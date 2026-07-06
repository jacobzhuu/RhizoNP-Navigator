from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from rhizonp.domain.models import LiteratureCorpusState, PaperChunk

_CORPUS_STATE_ID = 1
CHUNK_SCHEMA_VERSION = "paper_chunk_v2"


class CorpusStateNotInitializedError(RuntimeError):
    """Raised when the singleton literature corpus state row is missing."""


def compute_chunk_checksums(chunks: list[PaperChunk]) -> tuple[str, str, int]:
    ordered = sorted(chunks, key=lambda chunk: str(chunk.chunk_id))
    content_parts: list[str] = []
    id_parts: list[str] = []
    for chunk in ordered:
        chunk_id = str(chunk.chunk_id)
        id_parts.append(chunk_id)
        content_parts.append(
            "|".join(
                [
                    chunk_id,
                    str(chunk.paper_id),
                    chunk.section,
                    str(chunk.char_start),
                    str(chunk.char_end),
                    chunk.source_hash,
                    chunk.text,
                ]
            )
        )
    content_checksum = hashlib.sha256("\n".join(content_parts).encode()).hexdigest()
    ordered_ids_checksum = hashlib.sha256("\n".join(id_parts).encode()).hexdigest()
    return content_checksum, ordered_ids_checksum, len(ordered)


def compute_corpus_checksums_from_session(session: Session) -> tuple[str, str, int]:
    chunks = list(session.scalars(select(PaperChunk).order_by(PaperChunk.chunk_id)))
    return compute_chunk_checksums(chunks)


def get_corpus_revision(session: Session) -> int:
    state = session.get(LiteratureCorpusState, _CORPUS_STATE_ID)
    if state is None:
        raise CorpusStateNotInitializedError(
            "literature_corpus_state singleton row is not initialized (expected id=1)."
        )
    return int(state.corpus_revision)


def get_corpus_state(session: Session) -> LiteratureCorpusState:
    state = session.get(LiteratureCorpusState, _CORPUS_STATE_ID)
    if state is None:
        raise CorpusStateNotInitializedError(
            "literature_corpus_state singleton row is not initialized (expected id=1)."
        )
    return state


def ensure_corpus_state(session: Session) -> LiteratureCorpusState:
    state = session.get(LiteratureCorpusState, _CORPUS_STATE_ID)
    if state is not None:
        return state
    state = LiteratureCorpusState(
        id=_CORPUS_STATE_ID,
        corpus_revision=0,
        chunk_count=0,
        updated_at=datetime.now(timezone.utc),
    )
    session.add(state)
    session.flush()
    return state


def bump_corpus_revision(session: Session) -> int:
    content_checksum, ordered_chunk_ids_checksum, chunk_count = compute_corpus_checksums_from_session(
        session
    )
    state = ensure_corpus_state(session)
    state.corpus_revision = int(state.corpus_revision) + 1
    state.chunk_count = chunk_count
    state.content_checksum = content_checksum
    state.ordered_chunk_ids_checksum = ordered_chunk_ids_checksum
    state.updated_at = datetime.now(timezone.utc)
    session.flush()
    return int(state.corpus_revision)
