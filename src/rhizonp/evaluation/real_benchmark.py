from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from rhizonp.config import PROJECT_ROOT
from rhizonp.domain.models import Paper
from rhizonp.evaluation.retrieval_benchmark import (
    SystemRetrievalMetrics,
)
from rhizonp.evaluation.retrieval_metrics import (
    aggregate_metric,
    graded_mrr_at_k,
    graded_ndcg_at_k,
    graded_recall_at_k,
    strict_graded_mrr_at_k,
    strict_graded_recall_at_k,
)
from rhizonp.literature.embeddings import (
    HashingEmbeddingProvider,
    LiteratureEmbeddingProvider,
    create_literature_embedding_provider,
)
from rhizonp.literature.reranker import LiteratureReranker, create_literature_reranker
from rhizonp.literature.retrieval import SearchFilters, SearchResult, search_paper_chunks

DEFAULT_REAL_BENCHMARK_PATH = (
    PROJECT_ROOT / "data" / "eval" / "phase2_real_pubmed_benchmark.json"
)
VALID_RELEVANCE_GRADES = frozenset({0, 1, 2})


@dataclass(frozen=True)
class PaperRelevanceLabel:
    pmid: str
    grade: int
    annotator: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class RealBenchmarkQuery:
    query_id: str
    query: str
    category: str
    filters: SearchFilters = SearchFilters()
    labels: tuple[PaperRelevanceLabel, ...] = ()
    annotation_status: str = "pending"


@dataclass(frozen=True)
class RealBenchmarkSpec:
    benchmark_id: str
    description: str
    benchmark_type: str
    corpus_id: str | None
    queries: tuple[RealBenchmarkQuery, ...]


@dataclass(frozen=True)
class RealBenchmarkReport:
    benchmark_id: str
    description: str
    benchmark_type: str
    corpus_id: str | None
    annotation_status: str
    labeled_query_count: int
    systems: tuple[SystemRetrievalMetrics, ...] = ()


def _parse_filters(payload: Mapping[str, Any]) -> SearchFilters:
    filters_payload = payload.get("filters", {})
    return SearchFilters(
        year_from=filters_payload.get("year_from"),
        year_to=filters_payload.get("year_to"),
        sections=tuple(filters_payload.get("sections", [])),
        source_types=tuple(filters_payload.get("source_types", [])),
        dois=tuple(filters_payload.get("dois", [])),
        source_urls=tuple(filters_payload.get("source_urls", [])),
        journals=tuple(filters_payload.get("journals", [])),
        taxa=tuple(filters_payload.get("taxa", [])),
        compounds=tuple(filters_payload.get("compounds", [])),
        host=tuple(filters_payload.get("host", [])),
    )


def _parse_labels(entry: Mapping[str, Any]) -> tuple[PaperRelevanceLabel, ...]:
    labels: list[PaperRelevanceLabel] = []
    for label_entry in entry.get("labels", []):
        grade = int(label_entry["grade"])
        if grade not in VALID_RELEVANCE_GRADES:
            raise ValueError(f"Invalid relevance grade {grade}; expected 0, 1, or 2.")
        labels.append(
            PaperRelevanceLabel(
                pmid=str(label_entry["pmid"]),
                grade=grade,
                annotator=label_entry.get("annotator"),
                notes=label_entry.get("notes"),
            )
        )
    return tuple(labels)


def load_real_benchmark(path: str | Path) -> RealBenchmarkSpec:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("benchmark_type") != "real_pubmed":
        raise ValueError("Real benchmark file must set benchmark_type='real_pubmed'.")

    queries: list[RealBenchmarkQuery] = []
    for entry in payload.get("queries", []):
        queries.append(
            RealBenchmarkQuery(
                query_id=str(entry["query_id"]),
                query=str(entry["query"]),
                category=str(entry.get("category", "uncategorized")),
                filters=_parse_filters(entry),
                labels=_parse_labels(entry),
                annotation_status=str(entry.get("annotation_status", "pending")),
            )
        )
    return RealBenchmarkSpec(
        benchmark_id=str(payload["benchmark_id"]),
        description=str(payload.get("description", "")),
        benchmark_type=str(payload["benchmark_type"]),
        corpus_id=payload.get("corpus_id"),
        queries=tuple(queries),
    )


def benchmark_annotation_status(spec: RealBenchmarkSpec) -> str:
    if not spec.queries:
        return "empty"
    labeled = sum(1 for query in spec.queries if query.labels)
    if labeled == 0:
        return "pending"
    if labeled == len(spec.queries):
        return "complete"
    return "partial"


def _paper_id_to_pmid(session: Session) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for paper in session.scalars(select(Paper)):
        if paper.pmid:
            mapping[str(paper.paper_id)] = paper.pmid
    return mapping


def aggregate_results_to_papers(
    results: Sequence[SearchResult],
    paper_id_to_pmid: Mapping[str, str],
) -> list[tuple[str, float, int]]:
    """Aggregate chunk-level hits to paper-level by best score per PMID."""
    best_by_pmid: dict[str, tuple[float, int]] = {}
    for result in results:
        pmid = paper_id_to_pmid.get(str(result.paper_id))
        if not pmid:
            continue
        current = best_by_pmid.get(pmid)
        if current is None or result.score > current[0]:
            best_by_pmid[pmid] = (result.score, result.rank)
    ranked = sorted(
        best_by_pmid.items(),
        key=lambda item: (-item[1][0], item[1][1], item[0]),
    )
    return [(pmid, score, rank) for pmid, (score, rank) in ranked]


def _relevance_grades(labels: Sequence[PaperRelevanceLabel]) -> dict[str, int]:
    return {label.pmid: label.grade for label in labels}


def evaluate_real_retrieval_system(
    session: Session,
    benchmark: RealBenchmarkSpec,
    *,
    system_name: str,
    retrieval_mode: str,
    embedding_provider: LiteratureEmbeddingProvider | None = None,
    reranker: LiteratureReranker | None = None,
    top_k: int = 10,
) -> SystemRetrievalMetrics:
    paper_id_to_pmid = _paper_id_to_pmid(session)
    per_query: dict[str, dict[str, float]] = {}
    recalls_5: list[float] = []
    recalls_10: list[float] = []
    mrrs: list[float] = []
    ndcgs: list[float] = []

    for gold in benchmark.queries:
        if not gold.labels:
            continue

        results = search_paper_chunks(
            session,
            gold.query,
            top_k=top_k,
            filters=gold.filters,
            retrieval_mode=retrieval_mode,
            embedding_provider=embedding_provider,
            reranker=reranker,
        )
        paper_hits = aggregate_results_to_papers(results, paper_id_to_pmid)
        retrieved_pmids = [pmid for pmid, _, _ in paper_hits]
        grades = _relevance_grades(gold.labels)

        query_metrics = {
            "recall_at_5": graded_recall_at_k(grades, retrieved_pmids, 5),
            "recall_at_10": graded_recall_at_k(grades, retrieved_pmids, 10),
            "mrr_at_10": graded_mrr_at_k(grades, retrieved_pmids, 10),
            "ndcg_at_10": graded_ndcg_at_k(grades, retrieved_pmids, 10),
            "strict_recall_at_5": strict_graded_recall_at_k(grades, retrieved_pmids, 5),
            "strict_recall_at_10": strict_graded_recall_at_k(grades, retrieved_pmids, 10),
            "strict_mrr_at_10": strict_graded_mrr_at_k(grades, retrieved_pmids, 10),
        }
        per_query[gold.query_id] = query_metrics
        recalls_5.append(query_metrics["recall_at_5"])
        recalls_10.append(query_metrics["recall_at_10"])
        mrrs.append(query_metrics["mrr_at_10"])
        ndcgs.append(query_metrics["ndcg_at_10"])

    return SystemRetrievalMetrics(
        system_name=system_name,
        recall_at_5=aggregate_metric(recalls_5),
        recall_at_10=aggregate_metric(recalls_10),
        mrr_at_10=aggregate_metric(mrrs),
        ndcg_at_10=aggregate_metric(ndcgs),
        per_query=per_query,
    )


def run_real_retrieval_benchmark(
    session: Session,
    benchmark: RealBenchmarkSpec,
    *,
    include_model_dense: bool = False,
    include_bge_rerank: bool = False,
    embedding_provider_factory: Any | None = None,
    reranker_factory: Any | None = None,
) -> RealBenchmarkReport:
    labeled_count = sum(1 for query in benchmark.queries if query.labels)
    if labeled_count == 0:
        return RealBenchmarkReport(
            benchmark_id=benchmark.benchmark_id,
            description=benchmark.description,
            benchmark_type=benchmark.benchmark_type,
            corpus_id=benchmark.corpus_id,
            annotation_status=benchmark_annotation_status(benchmark),
            labeled_query_count=0,
            systems=(),
        )

    hashing_provider = HashingEmbeddingProvider(dimensions=128)
    lexical_reranker = create_literature_reranker("lexical")

    systems = [
        evaluate_real_retrieval_system(
            session,
            benchmark,
            system_name="bm25",
            retrieval_mode="bm25",
        ),
        evaluate_real_retrieval_system(
            session,
            benchmark,
            system_name="dense_hash",
            retrieval_mode="dense",
            embedding_provider=hashing_provider,
        ),
        evaluate_real_retrieval_system(
            session,
            benchmark,
            system_name="hybrid_hash",
            retrieval_mode="hybrid",
            embedding_provider=hashing_provider,
        ),
        evaluate_real_retrieval_system(
            session,
            benchmark,
            system_name="hybrid_rerank_lexical",
            retrieval_mode="hybrid_rerank",
            embedding_provider=hashing_provider,
            reranker=lexical_reranker,
        ),
    ]

    if include_model_dense:
        try:
            if embedding_provider_factory is not None:
                model_provider = embedding_provider_factory()
            else:
                model_provider = create_literature_embedding_provider("huggingface")
            systems.append(
                evaluate_real_retrieval_system(
                    session,
                    benchmark,
                    system_name="dense_model",
                    retrieval_mode="dense",
                    embedding_provider=model_provider,
                )
            )
            systems.append(
                evaluate_real_retrieval_system(
                    session,
                    benchmark,
                    system_name="hybrid_model",
                    retrieval_mode="hybrid",
                    embedding_provider=model_provider,
                )
            )
        except RuntimeError:
            pass

    if include_bge_rerank:
        try:
            if reranker_factory is not None:
                bge_reranker = reranker_factory()
            else:
                bge_reranker = create_literature_reranker("bge")
            systems.append(
                evaluate_real_retrieval_system(
                    session,
                    benchmark,
                    system_name="hybrid_rerank_bge",
                    retrieval_mode="hybrid_rerank",
                    embedding_provider=hashing_provider,
                    reranker=bge_reranker,
                )
            )
        except RuntimeError:
            pass

    return RealBenchmarkReport(
        benchmark_id=benchmark.benchmark_id,
        description=benchmark.description,
        benchmark_type=benchmark.benchmark_type,
        corpus_id=benchmark.corpus_id,
        annotation_status=benchmark_annotation_status(benchmark),
        labeled_query_count=labeled_count,
        systems=tuple(systems),
    )


def real_benchmark_report_to_dict(report: RealBenchmarkReport) -> dict[str, Any]:
    return {
        "benchmark_id": report.benchmark_id,
        "description": report.description,
        "benchmark_type": report.benchmark_type,
        "corpus_id": report.corpus_id,
        "annotation_status": report.annotation_status,
        "labeled_query_count": report.labeled_query_count,
        "systems": [
            {
                "system_name": system.system_name,
                "recall_at_5": system.recall_at_5,
                "recall_at_10": system.recall_at_10,
                "mrr_at_10": system.mrr_at_10,
                "ndcg_at_10": system.ndcg_at_10,
                "per_query": system.per_query,
            }
            for system in report.systems
        ],
    }
