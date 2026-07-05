from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select

from rhizonp.config import Settings
from rhizonp.domain.models import Base, PaperChunk
from rhizonp.ingestion.literature import load_phase2_literature_fixture
from rhizonp.literature.embeddings import HashingEmbeddingProvider
from rhizonp.literature.faiss_index import (
    FaissLiteratureVectorIndex,
    create_literature_vector_index,
    faiss_available,
)
from rhizonp.literature.vector_index import InMemoryLiteratureVectorIndex
from rhizonp.storage.postgres import create_session_factory, session_scope


def test_faiss_available_reports_optional_dependency() -> None:
    assert faiss_available() is False or faiss_available() is True


def test_faiss_index_raises_when_dependency_missing() -> None:
    if faiss_available():
        pytest.skip("faiss is installed in this environment")

    with pytest.raises(RuntimeError, match="faiss-cpu is required"):
        FaissLiteratureVectorIndex([])


def test_create_vector_index_factory_rejects_unknown_backend() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)
        chunks = list(session.scalars(select(PaperChunk)))

    with pytest.raises(ValueError, match="Unsupported literature_vector_index_backend"):
        create_literature_vector_index(
            "unknown",
            settings=Settings(literature_vector_index_backend="unknown"),
            chunks=chunks,
        )


@pytest.mark.skipif(not faiss_available(), reason="faiss-cpu is not installed")
def test_faiss_index_matches_in_memory_search_and_round_trips(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)
        chunks = list(session.scalars(select(PaperChunk).order_by(PaperChunk.paragraph_index)))
        provider = HashingEmbeddingProvider(dimensions=64)
        in_memory = InMemoryLiteratureVectorIndex.from_chunks(chunks, provider)
        faiss_index = FaissLiteratureVectorIndex.from_chunks(chunks, provider)
        query_vector = provider.embed("Streptomyces Feature_M123")

        in_memory_hits = in_memory.search(query_vector, top_k=3)
        faiss_hits = faiss_index.search(query_vector, top_k=3)

        output_dir = tmp_path / "faiss_index"
        faiss_index.save(output_dir)
        loaded_index = FaissLiteratureVectorIndex.load(output_dir)
        loaded_hits = loaded_index.search(query_vector, top_k=3)

    assert [hit.chunk_id for hit in faiss_hits] == [hit.chunk_id for hit in in_memory_hits]
    assert faiss_hits[0].metadata["doi"] == "10.0000/rhizonp.fixture.lit.001"
    assert faiss_hits[0].metadata["source_url"] == "https://example.org/rhizonp/fixture-literature-001"
    assert [hit.chunk_id for hit in loaded_hits] == [hit.chunk_id for hit in faiss_hits]


@pytest.mark.skipif(not faiss_available(), reason="faiss-cpu is not installed")
def test_faiss_index_respects_candidate_chunk_ids() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)
        chunks = list(session.scalars(select(PaperChunk).order_by(PaperChunk.paragraph_index)))
        discussion_chunk = next(chunk for chunk in chunks if chunk.section == "discussion")
        provider = HashingEmbeddingProvider(dimensions=64)
        index = FaissLiteratureVectorIndex.from_chunks(chunks, provider)

        hits = index.search(
            provider.embed("genus-level strain production"),
            top_k=10,
            candidate_chunk_ids={str(discussion_chunk.chunk_id)},
        )

    assert [hit.chunk_id for hit in hits] == [str(discussion_chunk.chunk_id)]
    assert hits[0].metadata["section"] == "discussion"


@pytest.mark.skipif(not faiss_available(), reason="faiss-cpu is not installed")
def test_create_vector_index_factory_builds_faiss_backend() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)
        chunks = list(session.scalars(select(PaperChunk)))

    index = create_literature_vector_index(
        "faiss",
        settings=Settings(literature_vector_index_backend="faiss"),
        chunks=chunks,
        embedding_provider=HashingEmbeddingProvider(dimensions=64),
    )

    assert index.index_name == "faiss"
