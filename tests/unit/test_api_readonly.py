from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import quote

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from rhizonp.api.app import create_app, get_session
from rhizonp.domain.models import Base
from rhizonp.ingestion.fixtures import load_phase1_demo_fixture
from rhizonp.storage.postgres import create_session_factory, session_scope


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

    def override_get_session() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    api.dependency_overrides[get_session] = override_get_session
    return TestClient(api)


def test_health_endpoint_does_not_require_database_url() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
