"""Literature ingestion and retrieval utilities for Phase 2."""

from rhizonp.literature.adapters import (
    NormalizedLiteratureRecord,
    RawLiteratureRecord,
    SourceAdapter,
    SyntheticLiteratureAdapter,
)
from rhizonp.literature.chunking import StructuredChunk, structured_chunk_record
from rhizonp.literature.embeddings import (
    HashingEmbeddingProvider,
    HuggingFaceLiteratureEmbeddingProvider,
    LiteratureEmbeddingProvider,
    create_literature_embedding_provider,
)
from rhizonp.literature.retrieval import (
    HybridWeights,
    LexicalOverlapReranker,
    SearchFilters,
    SearchResult,
    bm25_search,
    dense_search,
    hybrid_search,
    indexed_dense_search,
    persist_retrieval_results,
    rerank_search_results,
    search_paper_chunks,
)
from rhizonp.literature.vector_index import (
    InMemoryLiteratureVectorIndex,
    LiteratureVectorIndex,
    VectorIndexEntry,
    VectorIndexHit,
)

__all__ = [
    "HashingEmbeddingProvider",
    "HuggingFaceLiteratureEmbeddingProvider",
    "HybridWeights",
    "InMemoryLiteratureVectorIndex",
    "LexicalOverlapReranker",
    "LiteratureEmbeddingProvider",
    "LiteratureVectorIndex",
    "NormalizedLiteratureRecord",
    "RawLiteratureRecord",
    "SearchFilters",
    "SearchResult",
    "SourceAdapter",
    "StructuredChunk",
    "SyntheticLiteratureAdapter",
    "VectorIndexEntry",
    "VectorIndexHit",
    "bm25_search",
    "create_literature_embedding_provider",
    "dense_search",
    "hybrid_search",
    "indexed_dense_search",
    "persist_retrieval_results",
    "rerank_search_results",
    "search_paper_chunks",
    "structured_chunk_record",
]
