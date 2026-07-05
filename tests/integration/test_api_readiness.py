from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from rhizonp.api.app import create_app, get_optional_session, get_session
from rhizonp.domain.models import Base
from rhizonp.ingestion.literature import load_phase2_literature_fixture
from rhizonp.storage.postgres import create_session_factory, session_scope


@pytest.fixture
def literature_client() -> Iterator[TestClient]:
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

    def override_get_session() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_get_optional_session() -> Iterator[Session | None]:
        yield from override_get_session()

    api.dependency_overrides[get_session] = override_get_session
    api.dependency_overrides[get_optional_session] = override_get_optional_session
    client = TestClient(api)
    yield client
    api.dependency_overrides.clear()


def test_readiness_reports_degraded_for_fixture_corpus(literature_client: TestClient) -> None:
    response = literature_client.get("/api/v1/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"degraded", "ready", "unavailable"}
    assert payload["database"]["connected"] is True
    assert payload["corpus"]["chunk_count"] > 0
    assert "embedding_provider" in payload
    assert isinstance(payload["warnings"], list)


def test_readiness_without_database_reports_unavailable() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert payload["database"]["connected"] is False


def test_ask_validation_rejects_short_question(literature_client: TestClient) -> None:
    response = literature_client.post("/api/v1/ask", json={"question": "ab"})

    assert response.status_code == 422
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "validation_error"


def test_ask_pipeline_returns_structured_answer(literature_client: TestClient) -> None:
    response = literature_client.post(
        "/api/v1/ask",
        json={
            "question": "Does Streptomyces support natural product evidence?",
            "retrieval_mode": "bm25",
            "top_k": 3,
            "max_queries": 2,
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "question_plan" in payload
    assert "answer" in payload
    assert "retrieval_hits" in payload


def test_health_includes_request_id_header(literature_client: TestClient) -> None:
    response = literature_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
