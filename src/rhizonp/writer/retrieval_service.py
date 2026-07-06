from __future__ import annotations

from sqlalchemy.orm import Session

from rhizonp.literature.default_runtime import get_default_literature_runtime
from rhizonp.literature.retrieval import SearchFilters
from rhizonp.literature.service import LiteratureRetrievalService
from rhizonp.omics.literature_bridge import LiteratureEvidenceHit, search_result_to_evidence_hit


def retrieve_literature_evidence_hits(
    session: Session,
    query: str,
    *,
    query_taxon: str | None = None,
    observation_method: str | None = None,
    retrieval_mode: str = "bm25",
    top_k: int = 5,
    retrieval_service: LiteratureRetrievalService | None = None,
) -> list[LiteratureEvidenceHit]:
    service = retrieval_service or LiteratureRetrievalService(get_default_literature_runtime())
    results = service.search(
        session,
        query,
        top_k=top_k,
        filters=SearchFilters(),
        retrieval_mode=retrieval_mode,
    )
    taxon = query_taxon or query
    return [
        search_result_to_evidence_hit(
            session,
            result,
            query_text=query,
            query_index=index,
            retrieval_mode=retrieval_mode,
            query_taxon=taxon,
            observation_method=observation_method,
        )
        for index, result in enumerate(results, start=1)
    ]
