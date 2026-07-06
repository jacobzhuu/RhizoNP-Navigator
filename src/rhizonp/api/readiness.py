from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rhizonp.config import get_settings
from rhizonp.domain.models import Paper, PaperChunk
from rhizonp.literature.corpus_state import CorpusStateNotInitializedError, get_corpus_revision
from rhizonp.literature.index_store import is_index_stale, read_current_build_id
from rhizonp.literature.retrieval_settings import (
    PROFILE_OFFLINE,
    resolve_literature_retrieval_settings,
)
from rhizonp.writer.llm_writer import check_llm_configuration


def evaluate_readiness(session: Session | None) -> dict[str, object]:
    settings = get_settings()
    retrieval_settings = resolve_literature_retrieval_settings(settings)
    warnings: list[str] = []
    db_connected = False
    backend = "none"
    paper_count = 0
    chunk_count = 0
    real_chunk_count = 0
    corpus_revision: int | None = None
    index_stale = False
    faiss_index_loaded = False
    build_id: str | None = None

    if session is not None:
        try:
            session.scalar(select(func.count()).select_from(Paper))
            db_connected = True
            database_url = settings.database_url or ""
            if database_url.startswith("postgresql"):
                backend = "postgresql"
            elif database_url.startswith("sqlite"):
                backend = "sqlite"
            else:
                backend = "other"

            paper_count = int(session.scalar(select(func.count()).select_from(Paper)) or 0)
            chunks = list(session.scalars(select(PaperChunk)))
            chunk_count = len(chunks)
            for chunk in chunks:
                metadata = chunk.chunk_metadata or {}
                if metadata.get("fixture") is True:
                    continue
                real_chunk_count += 1
            try:
                corpus_revision = get_corpus_revision(session)
            except CorpusStateNotInitializedError:
                warnings.append("Literature corpus revision state is not initialized")
        except Exception:
            db_connected = False

    retrieval_profile = retrieval_settings.profile
    if retrieval_settings.profile != PROFILE_OFFLINE:
        build_id = read_current_build_id(retrieval_settings.faiss_index_path)
        faiss_index_loaded = build_id is not None
        if session is not None and db_connected:
            try:
                index_stale = is_index_stale(
                    session,
                    retrieval_settings.faiss_index_path,
                    settings=retrieval_settings,
                )
            except Exception:
                index_stale = True
        if not faiss_index_loaded:
            warnings.append("Literature FAISS CURRENT pointer is missing")
        elif index_stale:
            warnings.append("Literature FAISS index is stale relative to corpus revision")

    llm_report = check_llm_configuration()
    has_real_corpus = real_chunk_count > 0

    if not db_connected:
        status = "unavailable"
        warnings.append("Database is not connected")
    elif chunk_count == 0:
        status = "degraded"
        warnings.append("No literature chunks are loaded")
    elif retrieval_settings.profile != PROFILE_OFFLINE and (not faiss_index_loaded or index_stale):
        status = "degraded"
    elif not has_real_corpus:
        status = "degraded"
        warnings.append("Corpus contains only fixture chunks")
    elif retrieval_settings.embedding_provider == "hashing":
        status = "degraded"
        warnings.append("Using test embeddings; not for production retrieval claims")
    else:
        status = "ready"

    return {
        "status": status,
        "database": {"connected": db_connected, "backend": backend},
        "corpus": {
            "paper_count": paper_count,
            "chunk_count": chunk_count,
            "has_real_corpus": has_real_corpus,
            "corpus_revision": corpus_revision,
        },
        "retrieval_profile": retrieval_profile,
        "vector_index_backend": retrieval_settings.vector_index_backend,
        "faiss_index_loaded": faiss_index_loaded,
        "build_id": build_id,
        "index_stale": index_stale,
        "embedding_provider": retrieval_settings.embedding_provider,
        "embedding_model": retrieval_settings.embedding_model,
        "reranker": retrieval_settings.reranker,
        "llm_available": llm_report.get("api_key_present", False),
        "runtime_mode": settings.runtime_mode,
        "warnings": warnings,
    }
