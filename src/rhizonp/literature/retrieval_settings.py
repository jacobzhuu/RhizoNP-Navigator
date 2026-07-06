from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rhizonp.config import Settings, get_settings

PROFILE_OFFLINE = "offline"
PROFILE_STANDARD_RAG = "standard_rag"
PROFILE_CUSTOM = "custom"

_OFFLINE = {
    "embedding_provider": "hashing",
    "vector_index_backend": "in_memory",
    "reranker": "lexical",
}

_STANDARD_RAG = {
    "embedding_provider": "huggingface",
    "vector_index_backend": "faiss",
    "reranker": "bge",
}


@dataclass(frozen=True)
class ResolvedLiteratureRetrievalSettings:
    profile: str
    embedding_provider: str
    vector_index_backend: str
    reranker: str
    faiss_index_path: Path
    embedding_model: str
    reranker_model: str
    hashing_dimensions: int


def resolve_literature_retrieval_settings(
    settings: Settings | None = None,
) -> ResolvedLiteratureRetrievalSettings:
    resolved = settings or get_settings()
    profile = resolved.literature_retrieval_profile.casefold()

    if profile == PROFILE_OFFLINE:
        resolved_providers = dict(_OFFLINE)
    elif profile == PROFILE_STANDARD_RAG:
        resolved_providers = dict(_STANDARD_RAG)
    elif profile == PROFILE_CUSTOM:
        resolved_providers = {
            "embedding_provider": resolved.literature_embedding_provider,
            "vector_index_backend": resolved.literature_vector_index_backend,
            "reranker": resolved.literature_reranker,
        }
    else:
        raise ValueError(
            f"Unsupported literature_retrieval_profile {profile!r}. "
            f"Expected {PROFILE_OFFLINE!r}, {PROFILE_STANDARD_RAG!r}, or {PROFILE_CUSTOM!r}."
        )

    return ResolvedLiteratureRetrievalSettings(
        profile=profile,
        embedding_provider=resolved_providers["embedding_provider"].casefold(),
        vector_index_backend=resolved_providers["vector_index_backend"].casefold(),
        reranker=resolved_providers["reranker"].casefold(),
        faiss_index_path=Path(resolved.literature_faiss_index_path).expanduser().resolve(),
        embedding_model=resolved.embedding_model,
        reranker_model=resolved.reranker_model,
        hashing_dimensions=resolved.literature_hashing_dimensions,
    )
