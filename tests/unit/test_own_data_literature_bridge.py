from __future__ import annotations

from dataclasses import replace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from rhizonp.config import PROJECT_ROOT
from rhizonp.domain.models import Base
from rhizonp.ingestion.literature import load_phase2_literature_fixture
from rhizonp.literature.retrieval import bm25_search
from rhizonp.omics.csv_ingestion import load_own_data_bundle
from rhizonp.omics.literature_bridge import (
    DbBackedLiteratureRetriever,
    FixtureTestLiteratureRetriever,
    LiteratureEvidenceHit,
    LiteratureRetrievalStatus,
    retrieve_literature_for_association,
    search_result_to_evidence_hit,
)
from rhizonp.omics.pipeline import OwnDataPipelineOptions, run_own_data_pipeline
from rhizonp.omics.query_builder import (
    GeneratedQuery,
    QueryStrength,
    build_literature_queries,
    build_query_context,
)
from rhizonp.storage.postgres import create_session_factory


def _literature_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    load_phase2_literature_fixture(session)
    session.commit()
    return session


def _bundle():
    return load_own_data_bundle(PROJECT_ROOT / "data" / "fixtures" / "own_data_demo")


def test_query_builder_known_compound() -> None:
    bundle = _bundle()
    taxon = bundle.taxa[0]
    metabolite = next(item for item in bundle.metabolites if item.raw_label == "rapamycin")
    context = build_query_context(taxon, metabolite, association_score=0.55)
    queries = build_literature_queries(context)

    assert context.compound_identity_known is True
    assert queries[0].query_text == "Streptomyces Rapamycin"
    assert queries[1].query_text == "Streptomyces Rapamycin secondary metabolite"
    assert all(item.query_strength == QueryStrength.SPECIFIC for item in queries)


def test_query_builder_unknown_feature_does_not_use_feature_id() -> None:
    bundle = _bundle()
    taxon = bundle.taxa[0]
    metabolite = next(item for item in bundle.metabolites if item.raw_label == "Feature_M123")
    context = build_query_context(taxon, metabolite, association_score=0.72)
    queries = build_literature_queries(context)

    assert context.compound_identity_known is False
    assert all("Feature_M123" not in item.query_text for item in queries)
    assert queries[0].query_text == "Streptomyces secondary metabolites"
    assert queries[0].query_strength == QueryStrength.TAXON_FALLBACK


def test_query_builder_missing_metabolite_label_uses_taxon_fallback() -> None:
    bundle = _bundle()
    taxon = bundle.taxa[0]
    metabolite = next(item for item in bundle.metabolites if item.raw_label == "Feature_M123")
    metabolite = replace(
        metabolite,
        raw_label="",
        feature_id=None,
        chemical_identification_tier=None,
    )
    context = build_query_context(taxon, metabolite)
    queries = build_literature_queries(context, max_queries=2)

    assert queries
    assert all("Feature_" not in item.query_text for item in queries)


def test_query_builder_genus_level_taxon_still_builds_queries() -> None:
    bundle = _bundle()
    taxon = bundle.taxa[0]
    metabolite = next(item for item in bundle.metabolites if item.raw_label == "rapamycin")
    context = build_query_context(taxon, metabolite)
    queries = build_literature_queries(context)

    assert taxon.raw_label == "Streptomyces"
    assert queries[0].query_text.startswith("Streptomyces")


def test_search_result_to_evidence_hit_preserves_null_pmid_and_provenance() -> None:
    session = _literature_session()
    try:
        results = DbBackedLiteratureRetriever(session=session, top_k=1).retrieve_for_association(
            build_query_context(_bundle().taxa[0], _bundle().metabolites[0], association_score=0.72),
            query_taxon="Streptomyces",
            observation_method="synthetic_16S_fixture",
        )
        assert results.hits
        hit = results.hits[0]
        assert hit.chunk_id
        assert hit.paper_id
        assert hit.doi == "10.0000/rhizonp.fixture.lit.001"
        assert hit.pmid is None
        assert hit.provenance["trace"]["chunk_id"] == hit.chunk_id
    finally:
        session.close()


def test_pipeline_literature_disabled_status() -> None:
    result = run_own_data_pipeline(
        PROJECT_ROOT / "data" / "fixtures" / "own_data_demo",
        options=OwnDataPipelineOptions(enable_literature_retrieval=False),
    )
    literature = result.association_results[0].literature_retrieval
    assert literature["status"] == LiteratureRetrievalStatus.DISABLED.value
    assert literature["hits"] == []


def test_pipeline_literature_unavailable_without_session() -> None:
    result = run_own_data_pipeline(
        PROJECT_ROOT / "data" / "fixtures" / "own_data_demo",
        options=OwnDataPipelineOptions(enable_literature_retrieval=True),
    )
    literature = result.association_results[0].literature_retrieval
    assert literature["status"] == LiteratureRetrievalStatus.RETRIEVAL_UNAVAILABLE.value
    assert result.association_results[0].candidate_matrix.rows


def test_pipeline_literature_enabled_returns_hits_via_search_stack() -> None:
    session = _literature_session()
    try:
        result = run_own_data_pipeline(
            PROJECT_ROOT / "data" / "fixtures" / "own_data_demo",
            session=session,
            options=OwnDataPipelineOptions(
                enable_literature_retrieval=True,
                retrieval_mode="bm25",
                top_k=3,
            ),
        )
        feature_result = next(
            item
            for item in result.association_results
            if item.metabolite.raw_label == "Feature_M123"
        )
        literature = feature_result.literature_retrieval
        assert literature["status"] in {
            LiteratureRetrievalStatus.RETRIEVED.value,
            LiteratureRetrievalStatus.FIXTURE_TEST_ONLY.value,
        }
        assert literature["hits"]
        top_hit = literature["hits"][0]
        assert top_hit["chunk_id"]
        assert top_hit["paper_id"]
        assert top_hit["doi"] == "10.0000/rhizonp.fixture.lit.001"
        assert "Feature_M123" not in literature["queries"][0]["query_text"]
        assert feature_result.candidate_matrix.rows
    finally:
        session.close()


def test_pipeline_preserves_genus_taxonomy_warnings_with_literature() -> None:
    session = _literature_session()
    try:
        result = run_own_data_pipeline(
            PROJECT_ROOT / "data" / "fixtures" / "own_data_demo",
            session=session,
            options=OwnDataPipelineOptions(enable_literature_retrieval=True),
        )
        genus_result = next(
            item for item in result.association_results if item.taxon.raw_label == "Streptomyces"
        )
        assert genus_result.taxonomy_grading is not None
        assert genus_result.taxonomy_grading.max_supported_claim == "genus_level_candidate"
        assert genus_result.candidate_matrix.rows[0].status == "PARTIALLY_SUPPORTED"
        assert any("correlation" in item.casefold() for item in genus_result.limitations)
    finally:
        session.close()


def test_fixture_test_retriever_is_explicitly_marked() -> None:
    hit = LiteratureEvidenceHit(
        query_text="test",
        query_index=1,
        paper_id="paper",
        chunk_id="chunk",
        title="title",
        supporting_text="text",
        pmid=None,
        doi=None,
        source_url=None,
        journal=None,
        year=None,
        section="results",
        retrieval_mode="fixture_test",
        retrieval_score=1.0,
        matched_terms=[],
        provenance={},
        source_type="paper",
        is_fixture=True,
    )
    retriever = FixtureTestLiteratureRetriever(
        hits=[hit],
        queries=[GeneratedQuery("test", 1, "fixture", QueryStrength.WEAK)],
    )
    bundle = _bundle()
    context = build_query_context(bundle.taxa[0], bundle.metabolites[0])
    result = retrieve_literature_for_association(
        context,
        query_taxon="Streptomyces",
        observation_method=None,
        enabled=True,
        retriever=retriever,
    )
    assert result.status == LiteratureRetrievalStatus.FIXTURE_TEST_ONLY


def test_evidence_hit_does_not_fabricate_identifiers() -> None:
    session = _literature_session()
    try:
        results = bm25_search(session, "Streptomyces", top_k=1)
        assert results
        hit = search_result_to_evidence_hit(
            session,
            results[0],
            query_text="Streptomyces",
            query_index=1,
            retrieval_mode="bm25",
            query_taxon="Streptomyces",
            observation_method="synthetic_16S_fixture",
        )
        assert hit.pmid is None
        assert hit.doi is not None
    finally:
        session.close()
