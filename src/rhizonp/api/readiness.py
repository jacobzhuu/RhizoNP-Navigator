from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rhizonp.config import get_settings
from rhizonp.domain.models import Paper, PaperChunk


def evaluate_readiness(session: Session | None) -> dict[str, object]:
    settings = get_settings()
    warnings: list[str] = []
    db_connected = False
    backend = "none"
    paper_count = 0
    chunk_count = 0
    real_chunk_count = 0

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
        except Exception:
            db_connected = False

    has_real_corpus = real_chunk_count > 0
    embedding_provider = settings.literature_embedding_provider

    if embedding_provider == "hashing":
        warnings.append("Using test embeddings; not for production retrieval claims")

    if not db_connected:
        status = "unavailable"
        warnings.append("Database is not connected")
    elif chunk_count == 0:
        status = "degraded"
        warnings.append("No literature chunks are loaded")
    elif not has_real_corpus:
        status = "degraded"
        warnings.append("Corpus contains only fixture chunks")
    elif embedding_provider == "hashing":
        status = "degraded"
    else:
        status = "ready"

    return {
        "status": status,
        "database": {"connected": db_connected, "backend": backend},
        "corpus": {
            "paper_count": paper_count,
            "chunk_count": chunk_count,
            "has_real_corpus": has_real_corpus,
        },
        "embedding_provider": embedding_provider,
        "runtime_mode": settings.runtime_mode,
        "warnings": warnings,
    }
