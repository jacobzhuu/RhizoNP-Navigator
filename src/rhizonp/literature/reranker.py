from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, Protocol

from rhizonp.config import Settings, get_settings


class LiteratureReranker(Protocol):
    reranker_name: str

    def score(self, query: str, passages: list[str]) -> list[float]:
        ...


class NoOpLiteratureReranker:
    reranker_name = "none"

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [0.0 for _ in passages]


class LexicalOverlapReranker:
    reranker_name = "lexical"

    def score(self, query: str, passages: list[str]) -> list[float]:
        query_terms = set(_tokenize(query))
        if not query_terms:
            return [0.0 for _ in passages]
        return [
            len(query_terms.intersection(_tokenize(passage))) / len(query_terms)
            for passage in passages
        ]


class BGLiteratureReranker:
    """Optional BGE reranker for literature retrieval using FlagReranker."""

    reranker_name = "bge"

    def __init__(
        self,
        model_name: str,
        *,
        use_fp16: bool = True,
        model_factory: Callable[..., Any] | None = None,
    ) -> None:
        if not model_name.strip():
            raise ValueError("model_name must be a non-empty BGE reranker model ID.")
        from rhizonp.get_answer import BGEReranker

        self.model_name = model_name
        self._inner = BGEReranker(
            model_name,
            use_fp16=use_fp16,
            model_factory=model_factory,
        )

    def score(self, query: str, passages: list[str]) -> list[float]:
        return self._inner.score(query, passages)


def _tokenize(text: str) -> list[str]:
    return [token.casefold() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", text)]


def create_literature_reranker(
    reranker: str | None = None,
    *,
    settings: Settings | None = None,
    model_name: str | None = None,
    model_factory: Callable[..., Any] | None = None,
    use_fp16: bool = True,
) -> LiteratureReranker:
    resolved_settings = settings or get_settings()
    resolved_reranker = (reranker or resolved_settings.literature_reranker).casefold()

    if resolved_reranker in {"none", "noop", "no_op"}:
        return NoOpLiteratureReranker()
    if resolved_reranker in {"lexical", "lexical_overlap"}:
        return LexicalOverlapReranker()
    if resolved_reranker in {"bge", "cross_encoder"}:
        return BGLiteratureReranker(
            model_name or resolved_settings.reranker_model,
            use_fp16=use_fp16,
            model_factory=model_factory,
        )

    raise ValueError(
        "Unsupported literature_reranker "
        f"{resolved_reranker!r}. Expected 'none', 'lexical', or 'bge'."
    )
