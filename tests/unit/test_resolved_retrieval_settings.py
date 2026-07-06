from __future__ import annotations

from rhizonp.config import Settings
from rhizonp.literature.retrieval_settings import (
    PROFILE_CUSTOM,
    PROFILE_OFFLINE,
    PROFILE_STANDARD_RAG,
    resolve_literature_retrieval_settings,
)


def test_offline_profile_ignores_custom_provider_env() -> None:
    settings = Settings(
        literature_retrieval_profile=PROFILE_OFFLINE,
        literature_embedding_provider="huggingface",
        literature_vector_index_backend="faiss",
        literature_reranker="bge",
    )
    resolved = resolve_literature_retrieval_settings(settings)
    assert resolved.profile == PROFILE_OFFLINE
    assert resolved.embedding_provider == "hashing"
    assert resolved.vector_index_backend == "in_memory"
    assert resolved.reranker == "lexical"


def test_standard_rag_profile_uses_production_stack() -> None:
    settings = Settings(
        literature_retrieval_profile=PROFILE_STANDARD_RAG,
        literature_embedding_provider="hashing",
    )
    resolved = resolve_literature_retrieval_settings(settings)
    assert resolved.profile == PROFILE_STANDARD_RAG
    assert resolved.embedding_provider == "huggingface"
    assert resolved.vector_index_backend == "faiss"
    assert resolved.reranker == "bge"


def test_custom_profile_reads_explicit_env() -> None:
    settings = Settings(
        literature_retrieval_profile=PROFILE_CUSTOM,
        literature_embedding_provider="hashing",
        literature_vector_index_backend="in_memory",
        literature_reranker="lexical",
    )
    resolved = resolve_literature_retrieval_settings(settings)
    assert resolved.profile == PROFILE_CUSTOM
    assert resolved.embedding_provider == "hashing"
