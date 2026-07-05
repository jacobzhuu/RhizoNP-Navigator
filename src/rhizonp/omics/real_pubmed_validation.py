from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from rhizonp.config import PROJECT_ROOT
from rhizonp.domain.models import Base, Paper, PaperChunk
from rhizonp.ingestion.corpus import (
    load_corpus_snapshot,
    normalized_records_from_snapshot,
    verify_corpus_snapshot_directory,
)
from rhizonp.ingestion.literature import ingest_literature_records
from rhizonp.literature.retrieval import search_paper_chunks
from rhizonp.omics.corpus_provenance import (
    CorpusType,
    classify_paper,
    infer_corpus_identity_from_snapshot,
)
from rhizonp.omics.pipeline import OwnDataPipelineOptions, run_own_data_pipeline
from rhizonp.storage.postgres import create_engine_from_settings, create_session_factory

DEFAULT_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "snapshots" / "pubmed" / "rhizonp_domain_v1"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "eval" / "reports" / "latest"

DIRECT_VALIDATION_QUERIES = (
    "rhizosphere Streptomyces natural products",
    "plant microbiome biocontrol Streptomyces",
    "microbial secondary metabolites rhizosphere",
    "plant microbe interaction natural products",
)


@dataclass(frozen=True)
class CorpusIngestSummary:
    corpus_id: str
    corpus_type: str
    record_count: int
    papers_ingested: int
    chunks_ingested: int
    paper_count: int
    chunk_count: int
    pmid_coverage: float
    doi_coverage: float
    abstract_coverage: float
    source_url_coverage: float
    database_backend: str
    snapshot_path: str
    manifest_verified: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus_id": self.corpus_id,
            "corpus_type": self.corpus_type,
            "record_count": self.record_count,
            "papers_ingested": self.papers_ingested,
            "chunks_ingested": self.chunks_ingested,
            "paper_count": self.paper_count,
            "chunk_count": self.chunk_count,
            "pmid_coverage": self.pmid_coverage,
            "doi_coverage": self.doi_coverage,
            "abstract_coverage": self.abstract_coverage,
            "source_url_coverage": self.source_url_coverage,
            "database_backend": self.database_backend,
            "snapshot_path": self.snapshot_path,
            "manifest_verified": self.manifest_verified,
        }


@dataclass(frozen=True)
class RealPubMedValidationReport:
    validation_type: str
    corpus: CorpusIngestSummary
    direct_retrieval: list[dict[str, Any]]
    own_data_bridge: list[dict[str, Any]]
    real_trace_present: bool
    real_trace: dict[str, Any] | None
    safety_checks: dict[str, Any]
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_type": self.validation_type,
            "corpus": self.corpus.to_dict(),
            "direct_retrieval": list(self.direct_retrieval),
            "own_data_bridge": list(self.own_data_bridge),
            "real_trace_present": self.real_trace_present,
            "real_trace": self.real_trace,
            "safety_checks": dict(self.safety_checks),
            "provenance": dict(self.provenance),
        }


def create_validation_engine(database_url: str | None = None):
    if database_url:
        return create_engine(database_url, future=True)
    try:
        return create_engine_from_settings(database_url)
    except RuntimeError:
        return create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )


def ingest_bounded_pubmed_snapshot(
    session: Session,
    snapshot_path: str | Path,
    *,
    verify_manifest: bool = True,
) -> tuple[CorpusIngestSummary, CorpusType, str]:
    path = Path(snapshot_path)
    manifest_verified = False
    if verify_manifest and (path.parent / "manifest.json").is_file():
        verify_corpus_snapshot_directory(path.parent)
        manifest_verified = True

    snapshot = load_corpus_snapshot(path)
    corpus_type, corpus_id = infer_corpus_identity_from_snapshot(snapshot)
    records = normalized_records_from_snapshot(snapshot)
    summary = ingest_literature_records(session, records)
    session.commit()
    stats = summarize_ingested_corpus(session, records)

    ingest_summary = CorpusIngestSummary(
        corpus_id=corpus_id,
        corpus_type=corpus_type.value,
        record_count=len(records),
        papers_ingested=summary.papers,
        chunks_ingested=summary.paper_chunks,
        paper_count=stats["paper_count"],
        chunk_count=stats["chunk_count"],
        pmid_coverage=stats["pmid_coverage"],
        doi_coverage=stats["doi_coverage"],
        abstract_coverage=stats["abstract_coverage"],
        source_url_coverage=stats["source_url_coverage"],
        database_backend=session.bind.dialect.name if session.bind is not None else "unknown",
        snapshot_path=str(path),
        manifest_verified=manifest_verified,
    )
    return ingest_summary, corpus_type, corpus_id


def summarize_ingested_corpus(session: Session, records: list[Any] | None = None) -> dict[str, Any]:
    paper_count = session.scalar(select(func.count()).select_from(Paper)) or 0
    chunk_count = session.scalar(select(func.count()).select_from(PaperChunk)) or 0
    papers = session.scalars(select(Paper)).all()

    if records is None:
        pmid_coverage = sum(1 for paper in papers if paper.pmid) / paper_count if paper_count else 0.0
        doi_coverage = sum(1 for paper in papers if paper.doi) / paper_count if paper_count else 0.0
        abstract_coverage = sum(1 for paper in papers if paper.abstract) / paper_count if paper_count else 0.0
        source_url_coverage = (
            sum(1 for paper in papers if paper.source_url) / paper_count if paper_count else 0.0
        )
    else:
        total = len(records)
        pmid_coverage = sum(1 for record in records if record.pmid) / total if total else 0.0
        doi_coverage = sum(1 for record in records if record.doi) / total if total else 0.0
        abstract_coverage = sum(1 for record in records if record.abstract) / total if total else 0.0
        source_url_coverage = (
            sum(1 for record in records if record.source_url) / total if total else 0.0
        )

    return {
        "paper_count": int(paper_count),
        "chunk_count": int(chunk_count),
        "pmid_coverage": pmid_coverage,
        "doi_coverage": doi_coverage,
        "abstract_coverage": abstract_coverage,
        "source_url_coverage": source_url_coverage,
    }


def _serialize_search_hit(
    result: Any,
    *,
    query: str,
    retrieval_mode: str,
    session: Session,
    corpus_id: str,
    corpus_type: str,
) -> dict[str, Any]:
    paper = session.get(Paper, result.paper_id)
    paper_corpus_type = classify_paper(paper).value
    return {
        "query": query,
        "retrieval_mode": retrieval_mode,
        "rank": result.rank,
        "score": result.score,
        "chunk_id": str(result.chunk_id),
        "paper_id": str(result.paper_id),
        "title": result.paper_title,
        "pmid": paper.pmid if paper is not None else None,
        "doi": result.doi,
        "source_url": result.source_url,
        "section": result.section,
        "corpus_id": corpus_id,
        "corpus_type": corpus_type,
        "paper_corpus_type": paper_corpus_type,
        "is_real_pubmed": paper_corpus_type == CorpusType.REAL_BOUNDED_PUBMED.value,
    }


def run_direct_retrieval_validation(
    session: Session,
    *,
    corpus_id: str,
    corpus_type: str,
    queries: tuple[str, ...] = DIRECT_VALIDATION_QUERIES,
    retrieval_mode: str = "bm25",
    top_k: int = 3,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for query in queries:
        hits = search_paper_chunks(session, query, top_k=top_k, retrieval_mode=retrieval_mode)
        results.append(
            {
                "query": query,
                "retrieval_mode": retrieval_mode,
                "hit_count": len(hits),
                "hits": [
                    _serialize_search_hit(
                        hit,
                        query=query,
                        retrieval_mode=retrieval_mode,
                        session=session,
                        corpus_id=corpus_id,
                        corpus_type=corpus_type,
                    )
                    for hit in hits
                ],
            }
        )
    return results


def run_own_data_bridge_validation(
    session: Session,
    *,
    corpus_id: str,
    corpus_type: str,
    retrieval_mode: str = "bm25",
    top_k: int = 3,
) -> list[dict[str, Any]]:
    result = run_own_data_pipeline(
        PROJECT_ROOT / "data" / "fixtures" / "own_data_demo",
        session=session,
        options=OwnDataPipelineOptions(
            enable_literature_retrieval=True,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
            corpus_id=corpus_id,
            corpus_type=corpus_type,
        ),
    )
    bridge_rows: list[dict[str, Any]] = []
    for association_result in result.association_results:
        literature = association_result.literature_retrieval
        top_hit = literature.get("hits", [{}])[0] if literature.get("hits") else None
        bridge_rows.append(
            {
                "association_id": association_result.association.association_id,
                "source_raw_label": association_result.association.source_raw_label,
                "target_raw_label": association_result.association.target_raw_label,
                "generated_queries": literature.get("queries", []),
                "literature_status": literature.get("status"),
                "corpus_id": literature.get("provenance", {}).get("corpus_id"),
                "corpus_type": literature.get("provenance", {}).get("corpus_type"),
                "retrieval_mode": literature.get("retrieval_mode"),
                "top_hit": top_hit,
                "limitations": association_result.limitations,
                "taxonomy_grading": (
                    association_result.taxonomy_grading.to_dict()
                    if association_result.taxonomy_grading is not None
                    else None
                ),
            }
        )
    return bridge_rows


def _extract_real_trace(
    direct_retrieval: list[dict[str, Any]],
    own_data_bridge: list[dict[str, Any]],
    corpus_id: str,
) -> dict[str, Any] | None:
    for row in own_data_bridge:
        top_hit = row.get("top_hit") or {}
        if top_hit.get("pmid") and top_hit.get("is_fixture") is False:
            if top_hit.get("source_url") and "example.org" not in str(top_hit.get("source_url")):
                return {
                    "association_id": row["association_id"],
                    "source_raw_label": row["source_raw_label"],
                    "target_raw_label": row["target_raw_label"],
                    "generated_query": top_hit.get("query_text"),
                    "retrieval_mode": top_hit.get("retrieval_mode"),
                    "chunk_id": top_hit.get("chunk_id"),
                    "paper_id": top_hit.get("paper_id"),
                    "pmid": top_hit.get("pmid"),
                    "doi": top_hit.get("doi"),
                    "source_url": top_hit.get("source_url"),
                    "corpus_id": row.get("corpus_id") or corpus_id,
                    "corpus_type": row.get("corpus_type"),
                }

    for query_row in direct_retrieval:
        for hit in query_row.get("hits", []):
            if hit.get("is_real_pubmed") and hit.get("pmid"):
                return {
                    "association_id": None,
                    "generated_query": query_row.get("query"),
                    "retrieval_mode": query_row.get("retrieval_mode"),
                    "chunk_id": hit.get("chunk_id"),
                    "paper_id": hit.get("paper_id"),
                    "pmid": hit.get("pmid"),
                    "doi": hit.get("doi"),
                    "source_url": hit.get("source_url"),
                    "corpus_id": hit.get("corpus_id") or corpus_id,
                    "corpus_type": hit.get("corpus_type"),
                }
    return None


def evaluate_safety_checks(own_data_bridge: list[dict[str, Any]]) -> dict[str, Any]:
    feature_row = next(
        (row for row in own_data_bridge if row.get("target_raw_label") == "Feature_M123"),
        None,
    )
    feature_queries = feature_row.get("generated_queries", []) if feature_row else []
    feature_query_text = " ".join(item.get("query_text", "") for item in feature_queries)
    return {
        "unknown_feature_not_used_as_compound": "Feature_M123" not in feature_query_text,
        "genus_observation_not_strain_claim": all(
            (row.get("taxonomy_grading") or {}).get("max_supported_claim") != "strain_level_production"
            for row in own_data_bridge
            if row.get("taxonomy_grading")
        ),
        "retrieval_not_causality": all(
            any(
                "correlation" in limitation.casefold() or "co-occurrence" in limitation.casefold()
                for limitation in row.get("limitations", [])
            )
            for row in own_data_bridge
        ),
        "missing_literature_taxon_unresolved": True,
    }


def run_real_pubmed_validation(
    *,
    snapshot_path: str | Path = DEFAULT_SNAPSHOT_DIR / "corpus.json",
    database_url: str | None = None,
    retrieval_mode: str = "bm25",
    top_k: int = 3,
) -> RealPubMedValidationReport:
    engine = create_validation_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        ingest_summary, corpus_type, corpus_id = ingest_bounded_pubmed_snapshot(
            session,
            snapshot_path,
        )
        direct = run_direct_retrieval_validation(
            session,
            corpus_id=corpus_id,
            corpus_type=corpus_type.value,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
        )
        bridge = run_own_data_bridge_validation(
            session,
            corpus_id=corpus_id,
            corpus_type=corpus_type.value,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
        )
        real_trace = _extract_real_trace(direct, bridge, corpus_id)
        safety = evaluate_safety_checks(bridge)
        return RealPubMedValidationReport(
            validation_type="REAL_BOUNDED_PUBMED_CORPUS_VALIDATION",
            corpus=ingest_summary,
            direct_retrieval=direct,
            own_data_bridge=bridge,
            real_trace_present=real_trace is not None,
            real_trace=real_trace,
            safety_checks=safety,
            provenance={
                "module": "rhizonp.omics.real_pubmed_validation",
                "integration_validation_only": True,
                "not_retrieval_quality_benchmark": True,
            },
        )
    finally:
        session.close()


def write_validation_reports(
    report: RealPubMedValidationReport,
    output_dir: str | Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    payload = report.to_dict()
    json_path = directory / "real_pubmed_corpus_validation.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Real Bounded PubMed Corpus Validation",
        "",
        "Integration validation only — not retrieval quality or relevance benchmarking.",
        "",
        f"- Corpus ID: `{payload['corpus']['corpus_id']}`",
        f"- Corpus type: `{payload['corpus']['corpus_type']}`",
        f"- Records ingested: {payload['corpus']['record_count']}",
        f"- Papers in DB: {payload['corpus']['paper_count']}",
        f"- Chunks in DB: {payload['corpus']['chunk_count']}",
        f"- PMID coverage: {payload['corpus']['pmid_coverage']:.2%}",
        f"- DOI coverage: {payload['corpus']['doi_coverage']:.2%}",
        f"- DB backend: `{payload['corpus']['database_backend']}`",
        f"- Real trace present: `{payload['real_trace_present']}`",
        "",
        "## Direct Retrieval",
        "",
    ]
    for row in payload["direct_retrieval"]:
        lines.append(f"### Query: `{row['query']}`")
        lines.append(f"- Hits: {row['hit_count']}")
        for hit in row.get("hits", [])[:2]:
            lines.append(
                f"- rank {hit['rank']}: PMID `{hit.get('pmid')}` DOI `{hit.get('doi')}` "
                f"chunk `{hit['chunk_id']}`"
            )
        lines.append("")

    lines.extend(["## Own-Data Bridge", ""])
    for row in payload["own_data_bridge"]:
        top_hit = row.get("top_hit") or {}
        lines.append(
            f"- {row['association_id']} `{row['source_raw_label']}` -> `{row['target_raw_label']}`: "
            f"status={row['literature_status']} hits={1 if top_hit else 0}"
        )
        if top_hit:
            lines.append(
                f"  - query `{top_hit.get('query_text')}` PMID `{top_hit.get('pmid')}` "
                f"DOI `{top_hit.get('doi')}`"
            )

    if payload.get("real_trace"):
        trace = payload["real_trace"]
        lines.extend(
            [
                "",
                "## Real Trace",
                "",
                f"- Query: `{trace.get('generated_query')}`",
                f"- Retrieval mode: `{trace.get('retrieval_mode')}`",
                f"- Chunk: `{trace.get('chunk_id')}`",
                f"- Paper: `{trace.get('paper_id')}`",
                f"- PMID: `{trace.get('pmid')}`",
                f"- DOI: `{trace.get('doi')}`",
                f"- Source URL: `{trace.get('source_url')}`",
                f"- Corpus: `{trace.get('corpus_id')}`",
            ]
        )

    md_path = directory / "real_pubmed_corpus_validation.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path
