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
from rhizonp.literature.faiss_index import (
    FaissLiteratureVectorIndex,
    create_literature_vector_index,
    faiss_available,
)
from rhizonp.literature.reranker import (
    BGLiteratureReranker,
    LexicalOverlapReranker,
    LiteratureReranker,
    NoOpLiteratureReranker,
    create_literature_reranker,
)
from rhizonp.literature.retrieval import (
    HybridWeights,
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
    "BGLiteratureReranker",
    "FaissLiteratureVectorIndex",
    "HashingEmbeddingProvider",
    "HuggingFaceLiteratureEmbeddingProvider",
    "HybridWeights",
    "InMemoryLiteratureVectorIndex",
    "LexicalOverlapReranker",
    "LiteratureEmbeddingProvider",
    "LiteratureReranker",
    "LiteratureVectorIndex",
    "NoOpLiteratureReranker",
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
    "create_literature_reranker",
    "create_literature_vector_index",
    "dense_search",
    "faiss_available",
    "hybrid_search",
    "indexed_dense_search",
    "persist_retrieval_results",
    "rerank_search_results",
    "search_paper_chunks",
    "structured_chunk_record",
]
