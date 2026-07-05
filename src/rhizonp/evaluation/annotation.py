from __future__ import annotations

import csv
import hashlib
import json
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from rhizonp.domain.models import Paper
from rhizonp.evaluation.pool_config import DEFAULT_POOL_DEPTH, DEFAULT_POOL_SYSTEMS, PoolSystemSpec
from rhizonp.evaluation.real_benchmark import (
    VALID_RELEVANCE_GRADES,
    RealBenchmarkSpec,
    load_real_benchmark,
)
from rhizonp.literature.embeddings import HashingEmbeddingProvider
from rhizonp.literature.reranker import create_literature_reranker
from rhizonp.literature.retrieval import SearchResult, search_paper_chunks

# Legacy single-system export columns (backward compatibility).
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

BLIND_REVIEWER_COLUMNS = (
    "annotation_item_id",
    "query_id",
    "query_text",
    "pmid",
    "title",
    "abstract",
    "doi",
    "grade",
    "notes",
)

PROVENANCE_SIDECAR_COLUMNS = (
    "annotation_item_id",
    "query_id",
    "pmid",
    "retrieval_system",
    "rank",
    "score",
)

QC_AUDIT_COLUMNS = (
    "qc_annotation_item_id",
    "source_annotation_item_id",
    "query_id",
    "pmid",
)

DEFAULT_BLIND_SHUFFLE_SEED = 20260705


@dataclass(frozen=True)
class SystemHitProvenance:
    retrieval_system: str
    rank: int
    score: float


@dataclass(frozen=True)
class PooledAnnotationCandidate:
    query_id: str
    query_text: str
    category: str
    pmid: str
    title: str
    abstract: str
    doi: str | None
    source_url: str | None
    retrieval_systems: tuple[str, ...]
    provenance_hits: tuple[SystemHitProvenance, ...]


@dataclass(frozen=True)
class AnnotationCandidate:
    """Legacy single-system candidate shape."""

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


@dataclass(frozen=True)
class BlindAnnotationItem:
    annotation_item_id: str
    query_id: str
    query_text: str
    pmid: str
    title: str
    abstract: str
    doi: str | None
    is_qc_duplicate: bool = False


@dataclass(frozen=True)
class QCAuditMapping:
    qc_annotation_item_id: str
    source_annotation_item_id: str
    query_id: str
    pmid: str


@dataclass(frozen=True)
class BlindExportBundle:
    items: tuple[BlindAnnotationItem, ...]
    candidates: tuple[PooledAnnotationCandidate, ...]
    item_ids_by_pmid: dict[tuple[str, str], str]
    qc_mappings: tuple[QCAuditMapping, ...]
    shuffle_seed: int
    qc_fraction: float


@dataclass(frozen=True)
class QCConsistencyReport:
    pair_count: int
    exact_agreement_count: int
    exact_agreement_rate: float
    weighted_agreement_rate: float
    pairs: tuple[dict[str, Any], ...]


def _paper_lookup(session: Session) -> dict[str, Paper]:
    return {str(paper.paper_id): paper for paper in session.scalars(select(Paper))}


def _best_paper_hit(
    results: Sequence[SearchResult],
    papers: Mapping[str, Paper],
) -> dict[str, tuple[SearchResult, Paper]]:
    best: dict[str, tuple[SearchResult, Paper]] = {}
    for result in results:
        paper = papers.get(str(result.paper_id))
        if paper is None or not paper.pmid:
            continue
        current = best.get(paper.pmid)
        if current is None or result.score > current[0].score:
            best[paper.pmid] = (result, paper)
    return best


def export_pooled_annotation_candidates(
    session: Session,
    benchmark: RealBenchmarkSpec,
    *,
    pool_systems: Sequence[PoolSystemSpec] = DEFAULT_POOL_SYSTEMS,
    pool_depth: int = DEFAULT_POOL_DEPTH,
) -> list[PooledAnnotationCandidate]:
    """Union top-k hits across multiple retrieval systems, deduplicated by query_id + PMID."""
    papers = _paper_lookup(session)
    hashing_provider = HashingEmbeddingProvider(dimensions=128)
    lexical_reranker = create_literature_reranker("lexical")
    pooled: list[PooledAnnotationCandidate] = []

    for query in benchmark.queries:
        merged: dict[str, dict[str, Any]] = {}

        for system in pool_systems:
            embedding_provider = None
            reranker = None
            if system.retrieval_mode in {"dense", "hybrid", "hybrid_rerank"}:
                embedding_provider = hashing_provider
            if system.retrieval_mode == "hybrid_rerank":
                reranker = lexical_reranker

            results = search_paper_chunks(
                session,
                query.query,
                top_k=pool_depth,
                filters=query.filters,
                retrieval_mode=system.retrieval_mode,
                embedding_provider=embedding_provider,
                reranker=reranker,
            )
            paper_hits = _best_paper_hit(results, papers)
            for pmid, (result, hit_paper) in paper_hits.items():
                entry = merged.setdefault(
                    pmid,
                    {
                        "paper": hit_paper,
                        "hits": [],
                    },
                )
                entry["hits"].append(
                    SystemHitProvenance(
                        retrieval_system=system.system_name,
                        rank=result.rank,
                        score=result.score,
                    )
                )

        for pmid in sorted(merged):
            entry = merged[pmid]
            record_paper: Paper = entry["paper"]
            system_hits: list[SystemHitProvenance] = entry["hits"]
            system_hits.sort(key=lambda hit: (hit.retrieval_system, hit.rank))
            systems = tuple(sorted({hit.retrieval_system for hit in system_hits}))
            pooled.append(
                PooledAnnotationCandidate(
                    query_id=query.query_id,
                    query_text=query.query,
                    category=query.category,
                    pmid=pmid,
                    title=record_paper.title,
                    abstract=record_paper.abstract or "",
                    doi=record_paper.doi,
                    source_url=record_paper.source_url,
                    retrieval_systems=systems,
                    provenance_hits=tuple(system_hits),
                )
            )

    return pooled


def stable_annotation_item_id(query_id: str, pmid: str) -> str:
    """Stable ID from query + PMID only; does not encode retrieval rank or score."""
    digest = hashlib.sha256(f"{query_id}:{pmid}".encode()).hexdigest()[:16]
    return f"ai_{query_id}_{digest}"


def qc_duplicate_annotation_item_id(source_item_id: str, *, qc_seed: int) -> str:
    digest = hashlib.sha256(f"{source_item_id}:{qc_seed}".encode()).hexdigest()[:12]
    return f"{source_item_id}_qc_{digest}"


def _query_shuffle_seed(base_seed: int, query_id: str) -> int:
    query_digest = hashlib.sha256(f"{base_seed}:{query_id}".encode()).hexdigest()
    return int(query_digest[:8], 16)


def shuffle_blind_items_within_query(
    items: Sequence[BlindAnnotationItem],
    *,
    shuffle_seed: int,
) -> list[BlindAnnotationItem]:
    """Randomize presentation order within each query using a deterministic seed."""
    grouped: dict[str, list[BlindAnnotationItem]] = {}
    for item in items:
        grouped.setdefault(item.query_id, []).append(item)

    shuffled: list[BlindAnnotationItem] = []
    for query_id in sorted(grouped):
        bucket = list(grouped[query_id])
        rng = random.Random(_query_shuffle_seed(shuffle_seed, query_id))
        rng.shuffle(bucket)
        shuffled.extend(bucket)
    return shuffled


def apply_qc_duplicates(
    items: Sequence[BlindAnnotationItem],
    *,
    qc_fraction: float,
    qc_seed: int,
) -> tuple[list[BlindAnnotationItem], list[QCAuditMapping]]:
    if qc_fraction <= 0.0:
        return list(items), []

    primary_items = [item for item in items if not item.is_qc_duplicate]
    if not primary_items:
        return list(items), []

    rng = random.Random(qc_seed)
    count = max(1, round(len(primary_items) * qc_fraction)) if qc_fraction > 0 else 0
    count = min(count, len(primary_items))
    selected = rng.sample(primary_items, k=count)

    qc_items: list[BlindAnnotationItem] = []
    mappings: list[QCAuditMapping] = []
    for source in selected:
        qc_id = qc_duplicate_annotation_item_id(source.annotation_item_id, qc_seed=qc_seed)
        qc_items.append(
            BlindAnnotationItem(
                annotation_item_id=qc_id,
                query_id=source.query_id,
                query_text=source.query_text,
                pmid=source.pmid,
                title=source.title,
                abstract=source.abstract,
                doi=source.doi,
                is_qc_duplicate=True,
            )
        )
        mappings.append(
            QCAuditMapping(
                qc_annotation_item_id=qc_id,
                source_annotation_item_id=source.annotation_item_id,
                query_id=source.query_id,
                pmid=source.pmid,
            )
        )

    combined = list(items) + qc_items
    return combined, mappings


def prepare_blind_annotation_export(
    candidates: Sequence[PooledAnnotationCandidate],
    *,
    shuffle_seed: int = DEFAULT_BLIND_SHUFFLE_SEED,
    qc_fraction: float = 0.0,
    qc_seed: int = DEFAULT_BLIND_SHUFFLE_SEED,
) -> BlindExportBundle:
    primary_items = [
        BlindAnnotationItem(
            annotation_item_id=stable_annotation_item_id(candidate.query_id, candidate.pmid),
            query_id=candidate.query_id,
            query_text=candidate.query_text,
            pmid=candidate.pmid,
            title=candidate.title,
            abstract=candidate.abstract,
            doi=candidate.doi,
            is_qc_duplicate=False,
        )
        for candidate in candidates
    ]
    shuffled = shuffle_blind_items_within_query(primary_items, shuffle_seed=shuffle_seed)
    with_qc, qc_mappings = apply_qc_duplicates(
        shuffled,
        qc_fraction=qc_fraction,
        qc_seed=qc_seed,
    )
    reshuffled = shuffle_blind_items_within_query(with_qc, shuffle_seed=shuffle_seed)
    item_ids = {
        (item.query_id, item.pmid): item.annotation_item_id
        for item in reshuffled
        if not item.is_qc_duplicate
    }
    return BlindExportBundle(
        items=tuple(reshuffled),
        candidates=tuple(candidates),
        item_ids_by_pmid=item_ids,
        qc_mappings=tuple(qc_mappings),
        shuffle_seed=shuffle_seed,
        qc_fraction=qc_fraction,
    )


def blind_items_to_rows(items: Sequence[BlindAnnotationItem]) -> list[dict[str, Any]]:
    return [
        {
            "annotation_item_id": item.annotation_item_id,
            "query_id": item.query_id,
            "query_text": item.query_text,
            "pmid": item.pmid,
            "title": item.title,
            "abstract": item.abstract,
            "doi": item.doi or "",
            "grade": "",
            "notes": "",
        }
        for item in items
    ]


def qc_mappings_to_rows(mappings: Sequence[QCAuditMapping]) -> list[dict[str, Any]]:
    return [
        {
            "qc_annotation_item_id": mapping.qc_annotation_item_id,
            "source_annotation_item_id": mapping.source_annotation_item_id,
            "query_id": mapping.query_id,
            "pmid": mapping.pmid,
        }
        for mapping in mappings
    ]


def report_qc_consistency(
    review_rows: Sequence[Mapping[str, Any]],
    qc_mappings: Sequence[QCAuditMapping],
) -> QCConsistencyReport:
    grades_by_item: dict[str, int] = {}
    for row in review_rows:
        parsed = _parse_review_row(row)
        if parsed is None:
            continue
        item_id = str(row.get("annotation_item_id") or "")
        if not item_id:
            continue
        grades_by_item[item_id] = parsed[2]

    pair_reports: list[dict[str, Any]] = []
    exact_agreements = 0
    weighted_total = 0.0
    for mapping in qc_mappings:
        source_grade = grades_by_item.get(mapping.source_annotation_item_id)
        qc_grade = grades_by_item.get(mapping.qc_annotation_item_id)
        if source_grade is None or qc_grade is None:
            continue
        exact = source_grade == qc_grade
        if exact:
            exact_agreements += 1
        weighted_total += 1.0 - (abs(source_grade - qc_grade) / 2.0)
        pair_reports.append(
            {
                "qc_annotation_item_id": mapping.qc_annotation_item_id,
                "source_annotation_item_id": mapping.source_annotation_item_id,
                "query_id": mapping.query_id,
                "pmid": mapping.pmid,
                "source_grade": source_grade,
                "qc_grade": qc_grade,
                "exact_agreement": exact,
                "weighted_agreement": 1.0 - (abs(source_grade - qc_grade) / 2.0),
            }
        )

    pair_count = len(pair_reports)
    return QCConsistencyReport(
        pair_count=pair_count,
        exact_agreement_count=exact_agreements,
        exact_agreement_rate=(exact_agreements / pair_count) if pair_count else 0.0,
        weighted_agreement_rate=(weighted_total / pair_count) if pair_count else 0.0,
        pairs=tuple(pair_reports),
    )


def export_annotation_candidates(
    session: Session,
    benchmark: RealBenchmarkSpec,
    *,
    retrieval_system: str = "hybrid_hash",
    retrieval_mode: str = "hybrid",
    top_k: int = 20,
) -> list[AnnotationCandidate]:
    """Legacy single-system export. Prefer ``export_pooled_annotation_candidates``."""
    papers = _paper_lookup(session)
    provider = HashingEmbeddingProvider(dimensions=128)
    lexical_reranker = create_literature_reranker("lexical")
    candidates: list[AnnotationCandidate] = []
    seen: set[tuple[str, str]] = set()

    embedding_provider = provider if retrieval_mode != "bm25" else None
    reranker = lexical_reranker if retrieval_mode == "hybrid_rerank" else None

    for query in benchmark.queries:
        results = search_paper_chunks(
            session,
            query.query,
            top_k=top_k,
            filters=query.filters,
            retrieval_mode=retrieval_mode,
            embedding_provider=embedding_provider,
            reranker=reranker,
        )
        for result in results:
            paper = papers.get(str(result.paper_id))
            if paper is None or not paper.pmid:
                continue
            key = (query.query_id, paper.pmid)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                AnnotationCandidate(
                    query_id=query.query_id,
                    query_text=query.query,
                    category=query.category,
                    retrieval_system=retrieval_system,
                    rank=result.rank,
                    score=result.score,
                    pmid=paper.pmid,
                    title=paper.title,
                    abstract=paper.abstract or "",
                    doi=paper.doi,
                    source_url=paper.source_url,
                )
            )
    return candidates


def pooled_candidates_to_blind_rows(
    candidates: Sequence[PooledAnnotationCandidate],
) -> list[dict[str, Any]]:
    return blind_items_to_rows(
        [
            BlindAnnotationItem(
                annotation_item_id=stable_annotation_item_id(candidate.query_id, candidate.pmid),
                query_id=candidate.query_id,
                query_text=candidate.query_text,
                pmid=candidate.pmid,
                title=candidate.title,
                abstract=candidate.abstract,
                doi=candidate.doi,
                is_qc_duplicate=False,
            )
            for candidate in candidates
        ]
    )


def pooled_candidates_to_provenance_rows(
    candidates: Sequence[PooledAnnotationCandidate],
    *,
    item_ids_by_pmid: Mapping[tuple[str, str], str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        item_id = (
            item_ids_by_pmid.get((candidate.query_id, candidate.pmid))
            if item_ids_by_pmid is not None
            else stable_annotation_item_id(candidate.query_id, candidate.pmid)
        )
        for hit in candidate.provenance_hits:
            rows.append(
                {
                    "annotation_item_id": item_id,
                    "query_id": candidate.query_id,
                    "pmid": candidate.pmid,
                    "retrieval_system": hit.retrieval_system,
                    "rank": hit.rank,
                    "score": hit.score,
                }
            )
    return rows


def write_blind_reviewer_sheet(
    path: str | Path,
    export: BlindExportBundle | Sequence[BlindAnnotationItem] | Sequence[PooledAnnotationCandidate],
    *,
    shuffle_seed: int = DEFAULT_BLIND_SHUFFLE_SEED,
    qc_fraction: float = 0.0,
    qc_seed: int = DEFAULT_BLIND_SHUFFLE_SEED,
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(export, BlindExportBundle):
        rows = blind_items_to_rows(export.items)
    elif export and isinstance(export[0], BlindAnnotationItem):
        rows = blind_items_to_rows(export)  # type: ignore[arg-type]
    else:
        bundle = prepare_blind_annotation_export(
            export,  # type: ignore[arg-type]
            shuffle_seed=shuffle_seed,
            qc_fraction=qc_fraction,
            qc_seed=qc_seed,
        )
        rows = blind_items_to_rows(bundle.items)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(BLIND_REVIEWER_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return output


def write_qc_audit_mapping(
    path: str | Path,
    mappings: Sequence[QCAuditMapping],
) -> Path | None:
    if not mappings:
        return None
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(QC_AUDIT_COLUMNS))
        writer.writeheader()
        writer.writerows(qc_mappings_to_rows(mappings))
    return output


def write_provenance_sidecar(
    path: str | Path,
    candidates: Sequence[PooledAnnotationCandidate] | BlindExportBundle,
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(candidates, BlindExportBundle):
        rows = pooled_candidates_to_provenance_rows(
            candidates.candidates,
            item_ids_by_pmid=candidates.item_ids_by_pmid,
        )
    else:
        rows = pooled_candidates_to_provenance_rows(candidates)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(PROVENANCE_SIDECAR_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return output


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


def filter_qc_rows_for_import(
    review_rows: Sequence[Mapping[str, Any]],
    qc_mappings: Sequence[QCAuditMapping],
) -> list[dict[str, Any]]:
    """Remove QC duplicate rows before benchmark import (one label per query_id + pmid)."""
    qc_ids = {mapping.qc_annotation_item_id for mapping in qc_mappings}
    filtered: list[dict[str, Any]] = []
    for row in review_rows:
        item_id = str(row.get("annotation_item_id") or "")
        if item_id and item_id in qc_ids:
            continue
        filtered.append(dict(row))
    return filtered


def _known_pmids(session: Session) -> set[str]:
    return {paper.pmid for paper in session.scalars(select(Paper)) if paper.pmid}


def _parse_review_row(row: Mapping[str, Any]) -> tuple[str, str, int, str | None, str | None] | None:
    grade_raw = row.get("grade")
    if grade_raw is None or str(grade_raw).strip() == "":
        return None
    grade = int(grade_raw)
    annotator = row.get("annotator") or None
    notes = row.get("notes") or None
    return (
        str(row["query_id"]),
        str(row["pmid"]),
        grade,
        annotator,
        notes,
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
    """Merge reviewed 0/1/2 labels from blind reviewer sheets into the real benchmark JSON."""
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
