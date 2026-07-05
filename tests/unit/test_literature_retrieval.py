from sqlalchemy import create_engine

from rhizonp.domain.models import Base
from rhizonp.ingestion.literature import load_phase2_literature_fixture
from rhizonp.literature.retrieval import SearchFilters, bm25_search, persist_retrieval_results
from rhizonp.storage.postgres import create_session_factory, session_scope
from rhizonp.storage.repositories import RetrievalResultRepository


def test_bm25_search_results_trace_chunk_to_paper_source() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)
        filters = SearchFilters(year_from=2020, sections=("results",), taxa=("Streptomyces",))
        results = bm25_search(
            session,
            "Streptomyces Feature_M123",
            top_k=3,
            filters=filters,
        )
        run = persist_retrieval_results(
            session,
            query="Streptomyces Feature_M123",
            results=results,
            filters=filters,
            parameters={"top_k": 3},
        )
        run_id = run.run_id

    assert results
    top_result = results[0]
    assert top_result.rank == 1
    assert top_result.doi == "10.0000/rhizonp.fixture.lit.001"
    assert top_result.source_url == "https://example.org/rhizonp/fixture-literature-001"
    assert top_result.trace["doi"] == "10.0000/rhizonp.fixture.lit.001"
    assert "streptomyces" in top_result.matched_terms

    with session_scope(session_factory) as session:
        persisted_results = RetrievalResultRepository(session).list_for_run(run_id)
        assert len(persisted_results) == len(results)
        persisted_top = persisted_results[0]
        assert persisted_top.chunk.paper.doi == "10.0000/rhizonp.fixture.lit.001"
        assert persisted_top.provenance["trace"]["chunk_id"] == str(top_result.chunk_id)


def test_bm25_search_respects_metadata_filters() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)
        blocked_by_year = bm25_search(
            session,
            "Streptomyces",
            filters=SearchFilters(year_from=2030),
        )
        blocked_by_taxon = bm25_search(
            session,
            "Streptomyces",
            filters=SearchFilters(taxa=("Bacillus",)),
        )

    assert blocked_by_year == []
    assert blocked_by_taxon == []
