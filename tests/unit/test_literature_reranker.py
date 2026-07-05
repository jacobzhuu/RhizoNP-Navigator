from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from rhizonp.config import Settings
from rhizonp.domain.models import Base
from rhizonp.ingestion.literature import load_phase2_literature_fixture
from rhizonp.literature.embeddings import HashingEmbeddingProvider
from rhizonp.literature.reranker import (
    BGLiteratureReranker,
    LexicalOverlapReranker,
    NoOpLiteratureReranker,
    create_literature_reranker,
)
from rhizonp.literature.retrieval import SearchFilters, search_paper_chunks
from rhizonp.storage.postgres import create_session_factory, session_scope


class FakeFlagReranker:
    def __init__(self, model_name: str, *, use_fp16: bool) -> None:
        self.model_name = model_name
        self.use_fp16 = use_fp16
        self.pairs: list[list[str]] = []

    def compute_score(self, pairs: list[list[str]]) -> list[float]:
        self.pairs = pairs
        return [float(len(passage)) for _query, passage in pairs]


def test_no_op_literature_reranker_returns_neutral_scores() -> None:
    reranker = NoOpLiteratureReranker()

    assert reranker.score("query", ["a", "bb"]) == [0.0, 0.0]
    assert reranker.reranker_name == "none"


def test_lexical_overlap_reranker_scores_overlap() -> None:
    reranker = LexicalOverlapReranker()

    scores = reranker.score("Streptomyces natural products", ["Streptomyces biocontrol", "unrelated"])

    assert scores[0] > scores[1]
    assert reranker.reranker_name == "lexical"


def test_bge_literature_reranker_uses_injected_factory() -> None:
    created: list[FakeFlagReranker] = []

    def factory(model_name: str, *, use_fp16: bool) -> FakeFlagReranker:
        model = FakeFlagReranker(model_name, use_fp16=use_fp16)
        created.append(model)
        return model

    reranker = BGLiteratureReranker(
        "BAAI/bge-reranker-v2-m3",
        model_factory=factory,
    )
    scores = reranker.score("streptomyces", ["short", "longer passage"])

    assert scores == [5.0, 14.0]
    assert created[0].model_name == "BAAI/bge-reranker-v2-m3"
    assert reranker.reranker_name == "bge"


def test_create_literature_reranker_defaults_to_lexical() -> None:
    reranker = create_literature_reranker(
        settings=Settings(literature_reranker="lexical"),
    )

    assert isinstance(reranker, LexicalOverlapReranker)


def test_create_literature_reranker_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="Unsupported literature_reranker"):
        create_literature_reranker(reranker="unknown")


def test_hybrid_rerank_search_uses_factory_default_reranker() -> None:
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
            reranker=create_literature_reranker(
                settings=Settings(literature_reranker="lexical"),
            ),
        )

    assert results
    assert "reranker" in results[0].score_components
    assert results[0].trace["doi"] == "10.0000/rhizonp.fixture.lit.001"
