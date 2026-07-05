from functools import lru_cache
from typing import Any

from .config import get_settings

_HuggingFaceEmbeddings: Any = None
try:
    from langchain_huggingface import HuggingFaceEmbeddings as _ImportedHuggingFaceEmbeddings

    _HuggingFaceEmbeddings = _ImportedHuggingFaceEmbeddings
except ImportError:  # pragma: no cover - exercised only in incomplete envs
    pass


embedding_model_dict = {
    "bge-large-zh": "BAAI/bge-large-zh-v1.5",
    "acge-embedding": "yangjhchs/acge_text_embedding",
    "gte-large-zh": "thenlper/gte-large-zh",
}

EMBEDDING_MODEL = "acge-embedding"


def resolve_embedding_model(model_name: str | None = None) -> str:
    configured_model = model_name or get_settings().embedding_model
    return embedding_model_dict.get(configured_model, configured_model)


@lru_cache
def get_embeddings(model_name: str | None = None) -> Any:
    if _HuggingFaceEmbeddings is None:
        raise RuntimeError(
            "langchain-huggingface is required for local embeddings. "
            "Install project dependencies before building or loading FAISS indexes."
        )
    return _HuggingFaceEmbeddings(
        model_name=resolve_embedding_model(model_name),
        multi_process=False,
    )


class LazyEmbeddings:
    """Proxy that preserves the legacy `embeddings` object without eager model load."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return get_embeddings().embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return get_embeddings().embed_query(text)

    def __getattr__(self, name: str) -> Any:
        return getattr(get_embeddings(), name)


embeddings = LazyEmbeddings()
