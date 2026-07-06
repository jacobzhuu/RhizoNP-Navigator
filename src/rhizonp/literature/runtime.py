from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rhizonp.literature.embeddings import (
    LiteratureEmbeddingProvider,
    create_literature_embedding_provider,
)
from rhizonp.literature.faiss_index import FaissLiteratureVectorIndex
from rhizonp.literature.index_store import (
    IndexNotFoundError,
    IndexStaleError,
    load_build_manifest,
    read_current_build_id,
    resolve_active_build_dir,
    validate_manifest_against_settings,
)
from rhizonp.literature.reranker import LiteratureReranker, create_literature_reranker
from rhizonp.literature.retrieval_settings import (
    PROFILE_OFFLINE,
    ResolvedLiteratureRetrievalSettings,
    resolve_literature_retrieval_settings,
)
from rhizonp.literature.vector_index import LiteratureVectorIndex


@dataclass(frozen=True)
class LiteratureRetrievalRuntime:
    settings: ResolvedLiteratureRetrievalSettings
    embedding_provider: LiteratureEmbeddingProvider
    reranker: LiteratureReranker
    vector_index: LiteratureVectorIndex | None
    corpus_revision: int | None
    build_id: str | None
    manifest: dict[str, Any] | None


def build_offline_literature_runtime(
    settings: ResolvedLiteratureRetrievalSettings | None = None,
) -> LiteratureRetrievalRuntime:
    resolved_settings = settings or resolve_literature_retrieval_settings()
    embedding_provider = create_literature_embedding_provider(
        provider=resolved_settings.embedding_provider,
        hashing_dimensions=resolved_settings.hashing_dimensions,
        model_name=resolved_settings.embedding_model,
    )
    reranker = create_literature_reranker(
        reranker=resolved_settings.reranker,
        model_name=resolved_settings.reranker_model,
    )
    return LiteratureRetrievalRuntime(
        settings=resolved_settings,
        embedding_provider=embedding_provider,
        reranker=reranker,
        vector_index=None,
        corpus_revision=None,
        build_id=None,
        manifest=None,
    )


def build_literature_retrieval_runtime(
    *,
    strict: bool = True,
    settings: ResolvedLiteratureRetrievalSettings | None = None,
) -> LiteratureRetrievalRuntime:
    resolved_settings = settings or resolve_literature_retrieval_settings()

    if resolved_settings.profile == PROFILE_OFFLINE:
        return build_offline_literature_runtime(resolved_settings)

    embedding_provider = create_literature_embedding_provider(
        provider=resolved_settings.embedding_provider,
        hashing_dimensions=resolved_settings.hashing_dimensions,
        model_name=resolved_settings.embedding_model,
    )
    reranker = create_literature_reranker(
        reranker=resolved_settings.reranker,
        model_name=resolved_settings.reranker_model,
    )

    index_root_path = resolved_settings.faiss_index_path
    build_id = read_current_build_id(index_root_path)
    if build_id is None:
        if strict:
            raise IndexNotFoundError(
                f"No literature FAISS CURRENT pointer under {index_root_path}. "
                "Run scripts/build_literature_faiss_index.py --if-stale first."
            )
        return LiteratureRetrievalRuntime(
            settings=resolved_settings,
            embedding_provider=embedding_provider,
            reranker=reranker,
            vector_index=None,
            corpus_revision=None,
            build_id=None,
            manifest=None,
        )

    try:
        build_dir = resolve_active_build_dir(index_root_path)
        manifest = load_build_manifest(build_dir)
        if not validate_manifest_against_settings(manifest, resolved_settings):
            raise IndexStaleError("Literature FAISS manifest does not match active retrieval settings.")
        vector_index = FaissLiteratureVectorIndex.load(build_dir)
        corpus = manifest.get("corpus") or {}
        return LiteratureRetrievalRuntime(
            settings=resolved_settings,
            embedding_provider=embedding_provider,
            reranker=reranker,
            vector_index=vector_index,
            corpus_revision=int(corpus.get("revision", 0)),
            build_id=str(manifest.get("build_id") or build_id),
            manifest=manifest,
        )
    except (IndexNotFoundError, IndexStaleError, ValueError):
        if strict:
            raise
        return LiteratureRetrievalRuntime(
            settings=resolved_settings,
            embedding_provider=embedding_provider,
            reranker=reranker,
            vector_index=None,
            corpus_revision=None,
            build_id=None,
            manifest=None,
        )
