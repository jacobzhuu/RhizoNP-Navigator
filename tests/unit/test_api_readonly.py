from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import quote

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from rhizonp.api.app import create_app, get_literature_retrieval_service, get_optional_session, get_session
from rhizonp.literature.runtime import build_offline_literature_runtime
from rhizonp.literature.service import LiteratureRetrievalService
from rhizonp.domain.models import Base
from rhizonp.ingestion.fixtures import load_phase1_demo_fixture
from rhizonp.ingestion.literature import load_phase2_literature_fixture
from rhizonp.storage.postgres import create_session_factory, session_scope


def _attach_literature_service(api) -> None:
    runtime = build_offline_literature_runtime()
    api.state.literature_runtime = runtime
    api.state.literature_retrieval_service = LiteratureRetrievalService(runtime)

    def override_literature_service() -> LiteratureRetrievalService:
        return api.state.literature_retrieval_service

    api.dependency_overrides[get_literature_retrieval_service] = override_literature_service


def _override_session_dependencies(api, session_factory) -> None:
    def override_get_session() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    api.dependency_overrides[get_session] = override_get_session
    api.dependency_overrides[get_optional_session] = override_get_session


def _client_with_phase1_fixture() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase1_demo_fixture(session)

    api = create_app()
    _attach_literature_service(api)
    _override_session_dependencies(api, session_factory)
    return TestClient(api)


def _client_with_phase2_literature_fixture() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)

    api = create_app()
    _attach_literature_service(api)
    _override_session_dependencies(api, session_factory)
    return TestClient(api)


def test_health_endpoint_does_not_require_database_url() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_taxonomy_grade_endpoint_backward_compatible_without_source() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/taxonomy/grade",
        json={
            "query_taxon": "Streptomyces",
            "literature_taxon": "Streptomyces",
            "observation_method": "synthetic_16S_fixture",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["taxonomy_distance"] == "SAME_GENUS"
    assert payload["evidence_tier"] == "C"
    assert "provenance" in payload


def test_taxonomy_grade_endpoint_accepts_taxonomy_source() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/taxonomy/grade",
        json={
            "query_taxon": "Streptomyces",
            "literature_taxon": "Streptomyces hygroscopicus OS-2",
            "observation_method": "synthetic_16S_fixture",
            "taxonomy_source": "fixture",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["taxonomy_distance"] == "SAME_GENUS"
    assert payload["provenance"]["taxonomy_source"] == "fixture"


def test_writer_answer_backward_compatible_with_manual_evidence() -> None:
    client = TestClient(create_app())
    evidence_id = "00000000-0000-4000-8000-000000000001"

    response = client.post(
        "/api/v1/writer/answer",
        json={
            "question": "Does this strain produce rapamycin?",
            "evidence_items": [
                {
                    "evidence_id": evidence_id,
                    "claim_type": "taxon_produces_compound",
                    "predicate": "PRODUCES",
                    "object_literal": "Rapamycin",
                    "evidence_tier": "A",
                    "supporting_span": "Synthetic supporting span.",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SUPPORTED"
    assert payload["claims"]


def test_writer_answer_can_retrieve_fixture_evidence() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/writer/answer",
        json={
            "question": "What literature mentions Streptomyces metabolites?",
            "retrieve_evidence": True,
            "retrieval_query": "Streptomyces rapamycin",
            "query_taxon": "Streptomyces",
            "retrieval_mode": "bm25",
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["citation_validation"] is not None
    assert payload["citation_validation"]["citation_ref_validity_rate"] == 1.0


def test_api_queries_fixture_taxon_and_compound() -> None:
    client = _client_with_phase1_fixture()

    taxon_response = client.get("/api/v1/taxa/streptomyces")
    compound_response = client.get("/api/v1/compounds/fixturepolyketide-a")
    missing_response = client.get("/api/v1/taxa/UnknownTaxon")

    assert taxon_response.status_code == 200
    taxon = taxon_response.json()
    assert taxon["canonical_name"] == "Streptomyces"
    assert taxon["rank"] == "genus"
    assert taxon["normalization_status"] == "resolved_exact"

    assert compound_response.status_code == 200
    compound = compound_response.json()
    assert compound["canonical_name"] == "FixturePolyketide-A"
    assert compound["structure_status"] == "unknown"

    assert missing_response.status_code == 404


def test_api_returns_evidence_and_candidate_boundaries() -> None:
    client = _client_with_phase1_fixture()

    evidence_response = client.get("/api/v1/taxa/Streptomyces/evidence")
    candidate_response = client.get("/api/v1/taxa/Streptomyces/candidate-links")

    assert evidence_response.status_code == 200
    evidence = evidence_response.json()
    assert len(evidence) == 1
    assert evidence[0]["evidence_tier"] == "same_genus"
    assert evidence[0]["directness"] == "indirect"
    assert evidence[0]["provenance"]["policy_note"] == "same genus only"

    assert candidate_response.status_code == 200
    candidates = candidate_response.json()
    assert len(candidates) == 1
    assert candidates[0]["status"] == "PARTIALLY_SUPPORTED"
    assert candidates[0]["taxonomy_distance"] == "same_genus"
    assert "genus-level" in candidates[0]["rationale"]["limitation"]


def test_api_queries_dataset_omics_associations_without_causal_claims() -> None:
    client = _client_with_phase1_fixture()
    dataset_name = quote("Synthetic root injury own-omics demo")

    response = client.get(f"/api/v1/datasets/{dataset_name}/omics-associations")

    assert response.status_code == 200
    associations = response.json()
    assert len(associations) == 1
    assert associations[0]["source_raw_label"] == "Streptomyces"
    assert associations[0]["target_raw_label"] == "Feature_M123"
    assert associations[0]["metadata"]["correlation_not_causation"] is True


def test_api_search_returns_traceable_literature_chunks() -> None:
    client = _client_with_phase2_literature_fixture()

    response = client.post(
        "/api/v1/search",
        json={
            "query": "Streptomyces Feature_M123",
            "top_k": 2,
            "filters": {
                "sections": ["results"],
                "source_types": ["paper"],
                "dois": ["10.0000/rhizonp.fixture.lit.001"],
                "journals": ["fixture"],
                "taxa": ["Streptomyces"],
                "compounds": ["FixturePolyketide-A"],
                "host": ["Synthetic plant"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_mode"] == "bm25"
    assert payload["results"]
    top_result = payload["results"][0]
    assert top_result["trace"]["doi"] == "10.0000/rhizonp.fixture.lit.001"
    assert top_result["trace"]["source_url"] == "https://example.org/rhizonp/fixture-literature-001"
    assert top_result["trace"]["section"] == "results"
    assert "streptomyces" in top_result["matched_terms"]


def test_api_search_metadata_filters_can_exclude_results() -> None:
    client = _client_with_phase2_literature_fixture()

    response = client.post(
        "/api/v1/search",
        json={
            "query": "Streptomyces",
            "filters": {"compounds": ["UnknownCompound"]},
        },
    )

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_api_search_supports_hybrid_rerank_mode() -> None:
    client = _client_with_phase2_literature_fixture()

    response = client.post(
        "/api/v1/search",
        json={
            "query": "Streptomyces Feature_M123 causality",
            "top_k": 2,
            "retrieval_mode": "hybrid_rerank",
            "reranker_weight": 0.5,
            "filters": {"taxa": ["Streptomyces"]},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_mode"] == "hybrid_rerank"
    assert payload["results"]
    assert "pre_rerank_score" in payload["results"][0]["score_components"]
    assert "reranker" in payload["results"][0]["score_components"]
    assert payload["results"][0]["trace"]["doi"] == "10.0000/rhizonp.fixture.lit.001"


def test_api_search_rejects_unsupported_retrieval_mode() -> None:
    client = _client_with_phase2_literature_fixture()

    response = client.post(
        "/api/v1/search",
        json={"query": "Streptomyces", "retrieval_mode": "unsupported"},
    )

    assert response.status_code == 400
    assert "Unsupported retrieval_mode" in response.json()["detail"]


def test_api_corpus_summary_describes_retrievable_literature_chunks() -> None:
    client = _client_with_phase2_literature_fixture()

    response = client.get("/api/v1/corpus/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["paper_count"] >= 1
    assert payload["paper_chunk_count"] >= 1
    assert payload["retrievable_tables"] == ["paper_chunks"]
    assert "bm25" in payload["retrieval_modes"]
    assert payload["section_counts"]
    assert payload["sample_papers"]


def test_api_ask_runs_unified_question_to_grounded_answer_workflow() -> None:
    client = _client_with_phase2_literature_fixture()

    response = client.post(
        "/api/v1/ask",
        json={
            "question": "检测到 Streptomyces 是否说明样本中存在天然产物生产证据？",
            "retrieval_mode": "bm25",
            "top_k": 3,
            "max_queries": 2,
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["question_plan"]["intent"] == "must_bound_claim"
    assert payload["question_plan"]["entities"]["taxa"] == ["Streptomyces"]
    assert payload["question_plan"]["planner_mode"] == "deterministic_domain_rules"
    assert any(
        query["query_type"] == "taxon_np_expansion"
        for query in payload["question_plan"]["planned_queries"]
    )
    assert payload["retrieval_mode"] == "bm25"
    assert payload["retrieval_hits"]
    assert payload["answer"]["status"] in {
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "INSUFFICIENT_EVIDENCE",
    }
    assert payload["citation_validation"]["citation_ref_validity_rate"] == 1.0


def test_api_own_data_pipeline_backward_compatible_empty_request() -> None:
    client = TestClient(create_app())

    response = client.post("/api/v1/own-data/pipeline", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["association_count"] == 2
    assert payload["results"][0]["literature_retrieval"]["status"] == "DISABLED"


def test_api_own_data_pipeline_literature_enabled_without_database_url() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/own-data/pipeline",
        json={
            "enable_literature_retrieval": True,
            "retrieval_mode": "bm25",
            "top_k": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    feature_result = next(
        item for item in payload["results"] if item["target_raw_label"] == "Feature_M123"
    )
    literature = feature_result["literature_retrieval"]
    assert literature["status"] in {"RETRIEVED", "FIXTURE_TEST_ONLY"}
    assert literature["hits"]
    assert literature["hits"][0]["doi"] == "10.0000/rhizonp.fixture.lit.001"


def test_results_interpret_single_finding_integrates_internal_modules() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/results/interpret",
        json={
            "taxon": "Streptomyces",
            "metabolite": "M1023",
            "association_direction": "positive",
            "effect_size": 0.72,
            "p_value": 0.003,
            "observation_method": "16S genus-level",
            "use_llm": False,
            "retrieval_mode": "bm25",
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["finding_count"] == 1
    interpretation = payload["interpretations"][0]
    assert interpretation["finding"]["taxon"] == "Streptomyces"
    assert interpretation["status"] in {
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "INSUFFICIENT_EVIDENCE",
        "CONFLICTING_EVIDENCE",
    }
    assert interpretation["supported_interpretation"]
    assert interpretation["unsupported_interpretation"]
    assert interpretation["reasoning"]
    detailed = interpretation["detailed_evidence"]
    assert detailed["taxonomy_grading"] is not None
    assert detailed["candidate_links"]["rows"]
    assert detailed["literature_retrieval"]["status"] in {"RETRIEVED", "FIXTURE_TEST_ONLY", "NO_RESULTS"}
    assert detailed["pipeline_grounded_writer"] is not None
    assert detailed["combined_evidence_count"] >= detailed["candidate_evidence_count"] >= 1
    assert interpretation["grounded_answer"]["answer"]
    assert payload["provenance"]["forced_literature_retrieval"] is True
    assert payload["provenance"]["forced_grounded_writer"] is True


def test_results_demo_interpretation_uses_fixture_without_exposing_path() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/results/demo",
        json={"use_llm": False, "retrieval_mode": "bm25", "top_k": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["finding_count"] >= 1
    interpretation = payload["interpretations"][0]
    assert interpretation["finding"]["taxon"]
    assert interpretation["literature_evidence"]["count"] >= 0
    assert interpretation["natural_product_records"]
    assert interpretation["grounded_answer"]["writer_mode"] in {
        "fallback",
        "deterministic_offline",
        "fallback_after_citation_failure",
        "fallback_after_constraint_violation",
        "fallback_after_schema_failure",
        "fallback_after_provider_error",
        "deepseek_applied",
        "deepseek_general_knowledge",
    }
    assert "data/fixtures" not in str(payload["interpretations"][0]["finding"])
