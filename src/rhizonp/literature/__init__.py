"""Literature ingestion and retrieval utilities for Phase 2."""

from rhizonp.literature.adapters import (
    NormalizedLiteratureRecord,
    RawLiteratureRecord,
    SourceAdapter,
    SyntheticLiteratureAdapter,
)
from rhizonp.literature.chunking import StructuredChunk, structured_chunk_record
from rhizonp.literature.retrieval import (
    SearchFilters,
    SearchResult,
    bm25_search,
    persist_retrieval_results,
)

__all__ = [
    "NormalizedLiteratureRecord",
    "RawLiteratureRecord",
    "SearchFilters",
    "SearchResult",
    "SourceAdapter",
    "StructuredChunk",
    "SyntheticLiteratureAdapter",
    "bm25_search",
    "persist_retrieval_results",
    "structured_chunk_record",
]
