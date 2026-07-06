from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from rhizonp.domain.models import Base, LiteratureCorpusState, Paper, PaperChunk
from rhizonp.literature.corpus_state import bump_corpus_revision, get_corpus_revision


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_singleton_corpus_state_bumps_revision() -> None:
    session = _session()
    try:
        session.add(
            LiteratureCorpusState(
                id=1,
                corpus_revision=0,
                chunk_count=0,
            )
        )
        session.flush()
        paper = Paper(title="fixture paper", provenance={"fixture": True})
        session.add(paper)
        session.flush()
        session.add(
            PaperChunk(
                paper=paper,
                section="abstract",
                paragraph_index=0,
                char_start=0,
                char_end=4,
                text="test",
                source_hash="abc123",
                chunk_metadata={"fixture": True},
            )
        )
        session.flush()
        revision = bump_corpus_revision(session)
        assert revision == 1
        assert get_corpus_revision(session) == 1
        revision_again = bump_corpus_revision(session)
        assert revision_again == 2
    finally:
        session.close()
