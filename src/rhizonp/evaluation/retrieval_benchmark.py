from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from rhizonp.config import PROJECT_ROOT
from rhizonp.evaluation.retrieval_metrics import (
    aggregate_metric,
    mrr_at_k,
    ndcg_at_k,
    recall_at_k,
)
from rhizonp.literature.embeddings import (
    HashingEmbeddingProvider,
    LiteratureEmbeddingProvider,
    create_literature_embedding_provider,
)
from rhizonp.literature.reranker import LiteratureReranker, create_literature_reranker
from rhizonp.literature.retrieval import SearchFilters, SearchResult, search_paper_chunks

DEFAULT_RETRIEVAL_GOLD_PATH = PROJECT_ROOT / "data" / "eval" / "phase2_retrieval_gold.json"


@dataclass(frozen=True)
class RetrievalQueryGold:
    query_id: str
    query: str
    relevant_source_hashes: tuple[str, ...]
    filters: SearchFilters = SearchFilters()
    must_abstain: bool = False


@dataclass(frozen=True)
class RetrievalBenchmarkSpec:
    benchmark_id: str
    description: str
    queries: tuple[RetrievalQueryGold, ...]


@dataclass(frozen=True)
class SystemRetrievalMetrics:
    system_name: str
    recall_at_5: float
    recall_at_10: float
    mrr_at_10: float
    ndcg_at_10: float
    per_query: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalBenchmarkReport:
    benchmark_id: str
    description: str
    systems: tuple[SystemRetrievalMetrics, ...]


def load_retrieval_benchmark(path: str | Path) -> RetrievalBenchmarkSpec:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    queries: list[RetrievalQueryGold] = []
    for entry in payload.get("queries", []):
        filters_payload = entry.get("filters", {})
        queries.append(
            RetrievalQueryGold(
                query_id=str(entry["query_id"]),
                query=str(entry["query"]),
                relevant_source_hashes=tuple(entry.get("relevant_source_hashes", [])),
                filters=SearchFilters(
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
                ),
                must_abstain=bool(entry.get("must_abstain", False)),
            )
        )
    return RetrievalBenchmarkSpec(
        benchmark_id=str(payload["benchmark_id"]),
        description=str(payload.get("description", "")),
        queries=tuple(queries),
    )


def _resolve_chunk_keys(results: Sequence[SearchResult]) -> list[str]:
    keys: list[str] = []
    for result in results:
        source_hash = result.score_components.get("source_hash")
        if isinstance(source_hash, str) and source_hash:
            keys.append(source_hash)
            continue
        keys.append(str(result.chunk_id))
    return keys


def evaluate_retrieval_system(
    session: Session,
    benchmark: RetrievalBenchmarkSpec,
    *,
    system_name: str,
    retrieval_mode: str,
    embedding_provider: LiteratureEmbeddingProvider | None = None,
    reranker: LiteratureReranker | None = None,
    top_k: int = 10,
) -> SystemRetrievalMetrics:
    per_query: dict[str, dict[str, float]] = {}
    recalls_5: list[float] = []
    recalls_10: list[float] = []
    mrrs: list[float] = []
    ndcgs: list[float] = []

    for gold in benchmark.queries:
        if gold.must_abstain:
            continue
        if not gold.relevant_source_hashes:
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
        retrieved = _resolve_chunk_keys(results)
        relevant = set(gold.relevant_source_hashes)
        query_metrics = {
            "recall_at_5": recall_at_k(relevant, retrieved, 5),
            "recall_at_10": recall_at_k(relevant, retrieved, 10),
            "mrr_at_10": mrr_at_k(relevant, retrieved, 10),
            "ndcg_at_10": ndcg_at_k(relevant, retrieved, 10),
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


def run_retrieval_benchmark(
    session: Session,
    benchmark: RetrievalBenchmarkSpec,
    *,
    include_model_dense: bool = False,
    include_bge_rerank: bool = False,
    embedding_provider_factory: Any | None = None,
    reranker_factory: Any | None = None,
) -> RetrievalBenchmarkReport:
    hashing_provider = HashingEmbeddingProvider(dimensions=128)
    lexical_reranker = create_literature_reranker("lexical")

    systems = [
        evaluate_retrieval_system(
            session,
            benchmark,
            system_name="bm25",
            retrieval_mode="bm25",
        ),
        evaluate_retrieval_system(
            session,
            benchmark,
            system_name="dense_hash",
            retrieval_mode="dense",
            embedding_provider=hashing_provider,
        ),
        evaluate_retrieval_system(
            session,
            benchmark,
            system_name="hybrid_hash",
            retrieval_mode="hybrid",
            embedding_provider=hashing_provider,
        ),
        evaluate_retrieval_system(
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
                evaluate_retrieval_system(
                    session,
                    benchmark,
                    system_name="dense_model",
                    retrieval_mode="dense",
                    embedding_provider=model_provider,
                )
            )
            systems.append(
                evaluate_retrieval_system(
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
                evaluate_retrieval_system(
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

    return RetrievalBenchmarkReport(
        benchmark_id=benchmark.benchmark_id,
        description=benchmark.description,
        systems=tuple(systems),
    )


def benchmark_report_to_dict(report: RetrievalBenchmarkReport) -> dict[str, Any]:
    return {
        "benchmark_id": report.benchmark_id,
        "description": report.description,
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
