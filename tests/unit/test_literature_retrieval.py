from sqlalchemy import create_engine

from rhizonp.domain.models import Base
from rhizonp.ingestion.literature import load_phase2_literature_fixture
from rhizonp.literature.embeddings import HashingEmbeddingProvider
from rhizonp.literature.reranker import LexicalOverlapReranker
from rhizonp.literature.retrieval import (
    SearchFilters,
    bm25_search,
    dense_search,
    hybrid_search,
    persist_retrieval_results,
    search_paper_chunks,
)
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
        allowed_by_rich_filters = bm25_search(
            session,
            "FixturePolyketide-A",
            filters=SearchFilters(
                year_from=2020,
                year_to=2026,
                sections=("results",),
                source_types=("paper",),
                dois=("10.0000/RHIZONP.FIXTURE.LIT.001",),
                source_urls=("https://example.org/rhizonp/fixture-literature-001",),
                journals=("fixture",),
                taxa=("Streptomyces",),
                compounds=("FixturePolyketide-A",),
                host=("Synthetic plant",),
            ),
        )
        blocked_by_compound = bm25_search(
            session,
            "FixturePolyketide-A",
            filters=SearchFilters(compounds=("UnknownCompound",)),
        )
        blocked_by_source_type = bm25_search(
            session,
            "Streptomyces",
            filters=SearchFilters(source_types=("dataset",)),
        )

    assert blocked_by_year == []
    assert blocked_by_taxon == []
    assert allowed_by_rich_filters
    assert allowed_by_rich_filters[0].section == "results"
    assert blocked_by_compound == []
    assert blocked_by_source_type == []


def test_dense_search_uses_deterministic_vectors_and_trace() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)
        results = dense_search(
            session,
            "genus-level strain production",
            filters=SearchFilters(sections=("discussion",)),
            embedding_provider=HashingEmbeddingProvider(dimensions=64),
        )

    assert results
    assert results[0].section == "discussion"
    assert results[0].score_components["embedding_provider"] == "hashing"
    assert results[0].trace["doi"] == "10.0000/rhizonp.fixture.lit.001"


def test_hybrid_search_records_bm25_and_dense_components() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)
        results = hybrid_search(
            session,
            "Streptomyces Feature_M123",
            filters=SearchFilters(sections=("results",), taxa=("Streptomyces",)),
            embedding_provider=HashingEmbeddingProvider(dimensions=64),
        )

    assert results
    assert results[0].score_components["hybrid"] == results[0].score
    assert results[0].score_components["bm25"] > 0
    assert results[0].score_components["dense"] > 0
    assert results[0].trace["source_url"] == "https://example.org/rhizonp/fixture-literature-001"


def test_hybrid_rerank_search_records_reranker_component() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)
        results = search_paper_chunks(
            session,
            "Streptomyces Feature_M123 causality",
            top_k=2,
            filters=SearchFilters(taxa=("Streptomyces",)),
            retrieval_mode="hybrid_rerank",
            embedding_provider=HashingEmbeddingProvider(dimensions=64),
            reranker=LexicalOverlapReranker(),
            reranker_weight=0.5,
        )

    assert results
    assert results[0].rank == 1
    assert "pre_rerank_score" in results[0].score_components
    assert "reranker" in results[0].score_components
    assert results[0].trace["doi"] == "10.0000/rhizonp.fixture.lit.001"
