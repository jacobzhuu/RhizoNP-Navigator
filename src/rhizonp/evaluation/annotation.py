from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from rhizonp.domain.models import Paper
from rhizonp.evaluation.real_benchmark import (
    VALID_RELEVANCE_GRADES,
    RealBenchmarkSpec,
    load_real_benchmark,
)
from rhizonp.literature.embeddings import HashingEmbeddingProvider
from rhizonp.literature.retrieval import SearchResult, search_paper_chunks

ANNOTATION_EXPORT_COLUMNS = (
    "query_id",
    "query_text",
    "category",
    "retrieval_system",
    "rank",
    "score",
    "pmid",
    "title",
    "abstract",
    "doi",
    "source_url",
    "grade",
    "annotator",
    "notes",
)


@dataclass(frozen=True)
class AnnotationCandidate:
    query_id: str
    query_text: str
    category: str
    retrieval_system: str
    rank: int
    score: float
    pmid: str
    title: str
    abstract: str
    doi: str | None
    source_url: str | None


@dataclass(frozen=True)
class AnnotationImportResult:
    queries_updated: int
    labels_imported: int
    duplicate_labels: tuple[str, ...]
    unknown_pmids: tuple[str, ...]
    invalid_grades: tuple[str, ...]


def _paper_lookup(session: Session) -> dict[str, Paper]:
    return {str(paper.paper_id): paper for paper in session.scalars(select(Paper))}


def _result_to_candidate(
    *,
    query_id: str,
    query_text: str,
    category: str,
    retrieval_system: str,
    result: SearchResult,
    paper: Paper,
) -> AnnotationCandidate | None:
    pmid = paper.pmid
    if not pmid:
        return None
    return AnnotationCandidate(
        query_id=query_id,
        query_text=query_text,
        category=category,
        retrieval_system=retrieval_system,
        rank=result.rank,
        score=result.score,
        pmid=pmid,
        title=paper.title,
        abstract=paper.abstract or "",
        doi=paper.doi,
        source_url=paper.source_url,
    )


def export_annotation_candidates(
    session: Session,
    benchmark: RealBenchmarkSpec,
    *,
    retrieval_system: str = "hybrid_hash",
    retrieval_mode: str = "hybrid",
    top_k: int = 20,
) -> list[AnnotationCandidate]:
    """Export paper-level candidate hits per benchmark query for human review."""
    papers = _paper_lookup(session)
    provider = HashingEmbeddingProvider(dimensions=128)
    candidates: list[AnnotationCandidate] = []
    seen: set[tuple[str, str]] = set()

    for query in benchmark.queries:
        results = search_paper_chunks(
            session,
            query.query,
            top_k=top_k,
            filters=query.filters,
            retrieval_mode=retrieval_mode,
            embedding_provider=provider if retrieval_mode != "bm25" else None,
        )
        for result in results:
            paper = papers.get(str(result.paper_id))
            if paper is None or not paper.pmid:
                continue
            key = (query.query_id, paper.pmid)
            if key in seen:
                continue
            seen.add(key)
            candidate = _result_to_candidate(
                query_id=query.query_id,
                query_text=query.query,
                category=query.category,
                retrieval_system=retrieval_system,
                result=result,
                paper=paper,
            )
            if candidate is not None:
                candidates.append(candidate)
    return candidates


def annotation_candidates_to_rows(
    candidates: Sequence[AnnotationCandidate],
) -> list[dict[str, Any]]:
    return [
        {
            "query_id": candidate.query_id,
            "query_text": candidate.query_text,
            "category": candidate.category,
            "retrieval_system": candidate.retrieval_system,
            "rank": candidate.rank,
            "score": candidate.score,
            "pmid": candidate.pmid,
            "title": candidate.title,
            "abstract": candidate.abstract,
            "doi": candidate.doi or "",
            "source_url": candidate.source_url or "",
            "grade": "",
            "annotator": "",
            "notes": "",
        }
        for candidate in candidates
    ]


def write_annotation_export_csv(path: str | Path, candidates: Sequence[AnnotationCandidate]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = annotation_candidates_to_rows(candidates)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ANNOTATION_EXPORT_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return output


def write_annotation_export_json(path: str | Path, candidates: Sequence[AnnotationCandidate]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "export_type": "annotation_candidates",
        "candidate_count": len(candidates),
        "candidates": annotation_candidates_to_rows(candidates),
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output


def _known_pmids(session: Session) -> set[str]:
    return {paper.pmid for paper in session.scalars(select(Paper)) if paper.pmid}


def _parse_review_row(row: Mapping[str, Any]) -> tuple[str, str, int, str | None, str | None] | None:
    grade_raw = row.get("grade")
    if grade_raw is None or str(grade_raw).strip() == "":
        return None
    grade = int(grade_raw)
    return (
        str(row["query_id"]),
        str(row["pmid"]),
        grade,
        row.get("annotator") or None,
        row.get("notes") or None,
    )


def _load_review_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return list(payload.get("labels", payload.get("candidates", [])))


def validate_imported_labels(
    session: Session,
    benchmark: RealBenchmarkSpec,
    review_rows: Sequence[Mapping[str, Any]],
) -> AnnotationImportResult:
    known = _known_pmids(session)
    valid_query_ids = {query.query_id for query in benchmark.queries}
    duplicate_labels: list[str] = []
    unknown_pmids: list[str] = []
    invalid_grades: list[str] = []
    seen: set[tuple[str, str]] = set()
    parsed: list[tuple[str, str, int, str | None, str | None]] = []

    for row in review_rows:
        parsed_row = _parse_review_row(row)
        if parsed_row is None:
            continue
        query_id, pmid, grade, annotator, notes = parsed_row
        if query_id not in valid_query_ids:
            continue
        if grade not in VALID_RELEVANCE_GRADES:
            invalid_grades.append(f"{query_id}:{pmid}:{grade}")
            continue
        key = (query_id, pmid)
        if key in seen:
            duplicate_labels.append(f"{query_id}:{pmid}")
            continue
        seen.add(key)
        if pmid not in known:
            unknown_pmids.append(pmid)
            continue
        parsed.append((query_id, pmid, grade, annotator, notes))

    return AnnotationImportResult(
        queries_updated=0,
        labels_imported=len(parsed),
        duplicate_labels=tuple(duplicate_labels),
        unknown_pmids=tuple(unknown_pmids),
        invalid_grades=tuple(invalid_grades),
    )


def import_annotation_labels(
    session: Session,
    benchmark_path: str | Path,
    review_path: str | Path,
    *,
    output_path: str | Path | None = None,
    reject_unknown_pmids: bool = True,
    reject_duplicates: bool = True,
) -> tuple[RealBenchmarkSpec, AnnotationImportResult]:
    """Merge reviewed 0/1/2 labels into the real benchmark JSON."""
    benchmark = load_real_benchmark(benchmark_path)
    review_rows = _load_review_rows(Path(review_path))

    validation = validate_imported_labels(session, benchmark, review_rows)
    if reject_duplicates and validation.duplicate_labels:
        raise ValueError(f"Duplicate labels found: {', '.join(validation.duplicate_labels)}")
    if reject_unknown_pmids and validation.unknown_pmids:
        raise ValueError(f"Unknown PMIDs in corpus: {', '.join(validation.unknown_pmids)}")
    if validation.invalid_grades:
        raise ValueError(f"Invalid grades: {', '.join(validation.invalid_grades)}")

    labels_by_query: dict[str, list[dict[str, Any]]] = {}
    for row in review_rows:
        parsed_row = _parse_review_row(row)
        if parsed_row is None:
            continue
        query_id, pmid, grade, annotator, notes = parsed_row
        if query_id not in {query.query_id for query in benchmark.queries}:
            continue
        if reject_unknown_pmids and pmid not in _known_pmids(session):
            continue
        label_entry: dict[str, Any] = {"pmid": pmid, "grade": grade}
        if annotator:
            label_entry["annotator"] = annotator
        if notes:
            label_entry["notes"] = notes
        labels_by_query.setdefault(query_id, []).append(label_entry)

    payload = json.loads(Path(benchmark_path).read_text(encoding="utf-8"))
    queries_updated = 0
    for entry in payload.get("queries", []):
        query_id = str(entry["query_id"])
        if query_id not in labels_by_query:
            continue
        entry["labels"] = labels_by_query[query_id]
        entry["annotation_status"] = "labeled"
        queries_updated += 1

    labeled_total = sum(1 for entry in payload.get("queries", []) if entry.get("labels"))
    total_queries = len(payload.get("queries", []))
    if labeled_total == 0:
        payload["annotation_status"] = "pending"
    elif labeled_total == total_queries:
        payload["annotation_status"] = "complete"
    else:
        payload["annotation_status"] = "partial"

    target = Path(output_path) if output_path else Path(benchmark_path)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    updated_benchmark = load_real_benchmark(target)
    result = AnnotationImportResult(
        queries_updated=queries_updated,
        labels_imported=validation.labels_imported,
        duplicate_labels=validation.duplicate_labels,
        unknown_pmids=validation.unknown_pmids,
        invalid_grades=validation.invalid_grades,
    )
    return updated_benchmark, result
