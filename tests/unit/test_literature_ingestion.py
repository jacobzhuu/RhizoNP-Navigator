from sqlalchemy import create_engine

from rhizonp.domain.models import Base
from rhizonp.ingestion.literature import load_phase2_literature_fixture
from rhizonp.storage.postgres import create_session_factory, session_scope
from rhizonp.storage.repositories import PaperChunkRepository, PaperRepository


def test_phase2_literature_fixture_loads_paper_chunks_with_trace() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        summary = load_phase2_literature_fixture(session)

    assert summary.papers == 1
    assert summary.paper_chunks >= 5

    with session_scope(session_factory) as session:
        paper = PaperRepository(session).find_by_doi("10.0000/rhizonp.fixture.lit.001")
        assert paper is not None
        assert paper.source_url == "https://example.org/rhizonp/fixture-literature-001"
        assert paper.provenance["not_real_literature"] is True

        chunks = PaperChunkRepository(session).list_for_paper(paper.paper_id)
        assert chunks
        assert all(chunk.paper_id == paper.paper_id for chunk in chunks)
        assert {chunk.section for chunk in chunks}.issuperset({"title", "abstract", "results"})
        assert chunks[0].paper.doi == "10.0000/rhizonp.fixture.lit.001"
        assert chunks[0].chunk_metadata["source_type"] == "paper"
