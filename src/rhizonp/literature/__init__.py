"""Literature ingestion and retrieval utilities for Phase 2."""

from rhizonp.literature.adapters import (
    NormalizedLiteratureRecord,
    RawLiteratureRecord,
    SourceAdapter,
    SyntheticLiteratureAdapter,
)
from rhizonp.literature.chunking import StructuredChunk, structured_chunk_record
from rhizonp.literature.retrieval import (
    HashingEmbeddingProvider,
    HybridWeights,
    LexicalOverlapReranker,
    SearchFilters,
    SearchResult,
    bm25_search,
    dense_search,
    hybrid_search,
    persist_retrieval_results,
    rerank_search_results,
    search_paper_chunks,
)

__all__ = [
    "HashingEmbeddingProvider",
    "HybridWeights",
    "LexicalOverlapReranker",
    "NormalizedLiteratureRecord",
    "RawLiteratureRecord",
    "SearchFilters",
    "SearchResult",
    "SourceAdapter",
    "StructuredChunk",
    "SyntheticLiteratureAdapter",
    "bm25_search",
    "dense_search",
    "hybrid_search",
    "persist_retrieval_results",
    "rerank_search_results",
    "search_paper_chunks",
    "structured_chunk_record",
]
