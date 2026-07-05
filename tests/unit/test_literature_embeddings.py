from __future__ import annotations

import pytest

from rhizonp.config import Settings
from rhizonp.literature.embeddings import (
    HashingEmbeddingProvider,
    HuggingFaceLiteratureEmbeddingProvider,
    create_literature_embedding_provider,
)


class FakeEmbedder:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.queries: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [1.0, 0.5, 0.25]


def test_hashing_embedding_provider_is_deterministic() -> None:
    provider = HashingEmbeddingProvider(dimensions=32)

    first = provider.embed("Streptomyces Feature_M123")
    second = provider.embed("Streptomyces Feature_M123")

    assert first == second
    assert len(first) == 32
    assert provider.provider_name == "hashing"


def test_huggingface_embedding_provider_uses_injected_factory() -> None:
    created: list[FakeEmbedder] = []

    def factory(model_name: str) -> FakeEmbedder:
        embedder = FakeEmbedder(model_name)
        created.append(embedder)
        return embedder

    provider = HuggingFaceLiteratureEmbeddingProvider(
        "BAAI/bge-large-zh-v1.5",
        embedder_factory=factory,
    )

    vector = provider.embed("Streptomyces natural products")

    assert vector == [1.0, 0.5, 0.25]
    assert created[0].model_name == "BAAI/bge-large-zh-v1.5"
    assert created[0].queries == ["Streptomyces natural products"]
    assert provider.provider_name == "huggingface"


def test_create_literature_embedding_provider_defaults_to_hashing() -> None:
    provider = create_literature_embedding_provider(
        settings=Settings(literature_embedding_provider="hashing"),
    )

    assert provider.provider_name == "hashing"
    assert len(provider.embed("test")) == Settings().literature_hashing_dimensions


def test_create_literature_embedding_provider_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported literature_embedding_provider"):
        create_literature_embedding_provider(provider="unknown-backend")


def test_huggingface_provider_requires_dependency_without_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rhizonp.literature.embeddings as embeddings_module

    monkeypatch.setattr(embeddings_module, "_HuggingFaceEmbeddings", None)
    provider = HuggingFaceLiteratureEmbeddingProvider("example/model")

    with pytest.raises(RuntimeError, match="langchain-huggingface"):
        provider.embed("query")
