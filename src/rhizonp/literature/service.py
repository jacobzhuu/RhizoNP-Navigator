from __future__ import annotations

from sqlalchemy.orm import Session

from rhizonp.literature.retrieval import (
    HybridWeights,
    SearchFilters,
    SearchResult,
    search_paper_chunks,
)
from rhizonp.literature.runtime import LiteratureRetrievalRuntime


class LiteratureRetrievalService:
    def __init__(self, runtime: LiteratureRetrievalRuntime) -> None:
        self._runtime = runtime

    @property
    def runtime(self) -> LiteratureRetrievalRuntime:
        return self._runtime

    def search(
        self,
        session: Session,
        query: str,
        *,
        retrieval_mode: str = "hybrid_rerank",
        top_k: int = 10,
        filters: SearchFilters | None = None,
        hybrid_weights: HybridWeights | None = None,
        reranker_weight: float = 1.0,
    ) -> list[SearchResult]:
        return search_paper_chunks(
            session,
            query,
            runtime=self._runtime,
            top_k=top_k,
            filters=filters,
            retrieval_mode=retrieval_mode,
            hybrid_weights=hybrid_weights,
            reranker_weight=reranker_weight,
        )
