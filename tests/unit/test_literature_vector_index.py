from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, select

from rhizonp.domain.models import Base, PaperChunk
from rhizonp.ingestion.literature import load_phase2_literature_fixture
from rhizonp.literature import (
    HashingEmbeddingProvider,
    InMemoryLiteratureVectorIndex,
    SearchFilters,
    dense_search,
    hybrid_search,
)
from rhizonp.storage.postgres import create_session_factory, session_scope


def test_in_memory_literature_vector_index_searches_and_round_trips(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)
        chunks = list(session.scalars(select(PaperChunk).order_by(PaperChunk.paragraph_index)))
        provider = HashingEmbeddingProvider(dimensions=64)
        index = InMemoryLiteratureVectorIndex.from_chunks(chunks, provider)
        query_vector = provider.embed("Streptomyces Feature_M123")

        hits = index.search(query_vector, top_k=3)
        output_path = tmp_path / "indexes" / "literature_index.json"
        index.save(output_path)
        loaded_index = InMemoryLiteratureVectorIndex.load(output_path)
        loaded_hits = loaded_index.search(query_vector, top_k=3)

    assert hits
    assert hits[0].metadata["doi"] == "10.0000/rhizonp.fixture.lit.001"
    assert hits[0].metadata["source_url"] == "https://example.org/rhizonp/fixture-literature-001"
    assert hits[0].metadata["source_type"] == "paper"
    assert hits[0].metadata["source_hash"]
    assert loaded_index.embedding_provider_name == "hashing"
    assert [hit.chunk_id for hit in loaded_hits] == [hit.chunk_id for hit in hits]


def test_vector_index_respects_candidate_chunk_ids() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)
        chunks = list(session.scalars(select(PaperChunk).order_by(PaperChunk.paragraph_index)))
        discussion_chunk = next(chunk for chunk in chunks if chunk.section == "discussion")
        provider = HashingEmbeddingProvider(dimensions=64)
        index = InMemoryLiteratureVectorIndex.from_chunks(chunks, provider)

        hits = index.search(
            provider.embed("genus-level strain production"),
            top_k=10,
            candidate_chunk_ids={str(discussion_chunk.chunk_id)},
        )

    assert [hit.chunk_id for hit in hits] == [str(discussion_chunk.chunk_id)]
    assert hits[0].metadata["section"] == "discussion"


def test_dense_search_can_use_prebuilt_vector_index_with_trace() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)
        chunks = list(session.scalars(select(PaperChunk).order_by(PaperChunk.paragraph_index)))
        provider = HashingEmbeddingProvider(dimensions=64)
        index = InMemoryLiteratureVectorIndex.from_chunks(chunks, provider)

        results = dense_search(
            session,
            "genus-level strain production",
            filters=SearchFilters(sections=("discussion",)),
            embedding_provider=provider,
            vector_index=index,
        )

    assert results
    assert results[0].section == "discussion"
    assert results[0].score_components["vector_index"] == "in_memory"
    assert results[0].score_components["embedding_provider"] == "hashing"
    assert results[0].trace["doi"] == "10.0000/rhizonp.fixture.lit.001"


def test_hybrid_search_can_use_prebuilt_vector_index() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)
        chunks = list(session.scalars(select(PaperChunk).order_by(PaperChunk.paragraph_index)))
        provider = HashingEmbeddingProvider(dimensions=64)
        index = InMemoryLiteratureVectorIndex.from_chunks(chunks, provider)

        results = hybrid_search(
            session,
            "Streptomyces Feature_M123",
            filters=SearchFilters(sections=("results",), taxa=("Streptomyces",)),
            embedding_provider=provider,
            vector_index=index,
        )

    assert results
    assert results[0].score_components["dense"] > 0
    assert results[0].score_components["vector_index"] == "in_memory"
    assert results[0].trace["source_url"] == "https://example.org/rhizonp/fixture-literature-001"
