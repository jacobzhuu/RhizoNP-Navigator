from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any, Protocol

from rhizonp.config import Settings, get_settings
from rhizonp.embedding import resolve_embedding_model

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:  # pragma: no cover - exercised only in incomplete envs
    HuggingFaceEmbeddings = None


class LiteratureEmbeddingProvider(Protocol):
    provider_name: str

    def embed(self, text: str) -> list[float]:
        ...


class HashingEmbeddingProvider:
    """Deterministic local embedding for tests and offline development."""

    provider_name = "hashing"

    def __init__(self, *, dimensions: int = 128) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _tokenize(text):
            digest = hashlib.sha256(token.encode()).hexdigest()
            index = int(digest[:8], 16) % self.dimensions
            vector[index] += 1.0
        return vector


class HuggingFaceLiteratureEmbeddingProvider:
    """Optional model-backed literature embeddings using HuggingFace model IDs."""

    provider_name = "huggingface"

    def __init__(
        self,
        model_name: str,
        *,
        embedder_factory: Callable[[str], Any] | None = None,
    ) -> None:
        if not model_name.strip():
            raise ValueError("model_name must be a non-empty HuggingFace model ID or local path.")
        self.model_name = resolve_embedding_model(model_name)
        self._embedder_factory = embedder_factory
        self._embedder: Any | None = None

    def _get_embedder(self) -> Any:
        if self._embedder is None:
            factory = self._embedder_factory or _default_huggingface_embedder_factory
            self._embedder = factory(self.model_name)
        return self._embedder

    def embed(self, text: str) -> list[float]:
        vector = self._get_embedder().embed_query(text)
        return [float(value) for value in vector]


def _default_huggingface_embedder_factory(model_name: str) -> Any:
    if HuggingFaceEmbeddings is None:
        raise RuntimeError(
            "langchain-huggingface is required for model-backed literature embeddings. "
            "Install project dependencies or use the hashing provider for offline tests."
        )
    return HuggingFaceEmbeddings(model_name=model_name, multi_process=False)


def _tokenize(text: str) -> list[str]:
    import re

    return [token.casefold() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", text)]


def create_literature_embedding_provider(
    provider: str | None = None,
    *,
    settings: Settings | None = None,
    model_name: str | None = None,
    hashing_dimensions: int | None = None,
    embedder_factory: Callable[[str], Any] | None = None,
) -> LiteratureEmbeddingProvider:
    resolved_settings = settings or get_settings()
    resolved_provider = (provider or resolved_settings.literature_embedding_provider).casefold()

    if resolved_provider == "hashing":
        dimensions = hashing_dimensions or resolved_settings.literature_hashing_dimensions
        return HashingEmbeddingProvider(dimensions=dimensions)

    if resolved_provider in {"huggingface", "model"}:
        resolved_model = model_name or resolved_settings.embedding_model
        return HuggingFaceLiteratureEmbeddingProvider(
            resolved_model,
            embedder_factory=embedder_factory,
        )

    raise ValueError(
        "Unsupported literature_embedding_provider "
        f"{resolved_provider!r}. Expected 'hashing' or 'huggingface'."
    )
