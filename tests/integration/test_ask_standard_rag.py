from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from rhizonp.api.app import create_app, get_literature_retrieval_service, get_session
from rhizonp.domain.models import Base, LiteratureCorpusState
from rhizonp.ingestion.literature import load_phase2_literature_fixture
from rhizonp.literature.embeddings import HashingEmbeddingProvider
from rhizonp.literature.reranker import LexicalOverlapReranker
from rhizonp.literature.runtime import LiteratureRetrievalRuntime, build_offline_literature_runtime
from rhizonp.literature.service import LiteratureRetrievalService
from rhizonp.storage.postgres import create_session_factory, session_scope


class _TrackingReranker(LexicalOverlapReranker):
    calls = 0

    def score(self, query: str, passages: list[str]) -> list[float]:
        type(self).calls += 1
        return super().score(query, passages)


@pytest.fixture
def ask_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    _TrackingReranker.calls = 0
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        session.add(LiteratureCorpusState(id=1, corpus_revision=0, chunk_count=0))
        session.flush()
        load_phase2_literature_fixture(session)

    offline = build_offline_literature_runtime()
    runtime = LiteratureRetrievalRuntime(
        settings=offline.settings,
        embedding_provider=HashingEmbeddingProvider(dimensions=offline.settings.hashing_dimensions),
        reranker=_TrackingReranker(),
        vector_index=None,
        corpus_revision=1,
        build_id=None,
        manifest=None,
    )
    api = create_app()
    api.state.literature_runtime = runtime
    api.state.literature_retrieval_service = LiteratureRetrievalService(runtime)

    def override_literature_service() -> LiteratureRetrievalService:
        return api.state.literature_retrieval_service

    def override_get_session() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    api.dependency_overrides[get_literature_retrieval_service] = override_literature_service
    api.dependency_overrides[get_session] = override_get_session

    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("QWEN_API_KEY", "")
    from rhizonp.config import get_settings

    get_settings.cache_clear()
    client = TestClient(api)
    yield client
    api.dependency_overrides.clear()


def test_ask_uses_reranker_and_returns_hits(ask_client: TestClient) -> None:
    response = ask_client.post(
        "/api/v1/ask",
        json={
            "question": "Streptomyces natural products in rhizosphere context",
            "retrieval_mode": "hybrid_rerank",
            "top_k": 3,
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_hits"]
    assert _TrackingReranker.calls >= 1
    assert payload["answer"]["writer_mode"] in {"fallback", "deterministic_fallback", "deterministic_offline"}


def test_search_endpoint_uses_retrieval_service(ask_client: TestClient) -> None:
    response = ask_client.post(
        "/api/v1/search",
        json={
            "query": "Streptomyces rhizosphere",
            "retrieval_mode": "hybrid_rerank",
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]
