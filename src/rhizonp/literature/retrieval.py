from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rhizonp.domain.models import Paper, PaperChunk, RetrievalResult, RetrievalRun
from rhizonp.literature.default_runtime import get_default_literature_runtime
from rhizonp.literature.embeddings import (
    HashingEmbeddingProvider,
    LiteratureEmbeddingProvider,
)
from rhizonp.literature.reranker import (
    LiteratureReranker,
    create_literature_reranker,
)
from rhizonp.literature.runtime import LiteratureRetrievalRuntime
from rhizonp.literature.vector_index import InMemoryLiteratureVectorIndex, LiteratureVectorIndex


@dataclass(frozen=True)
class SearchFilters:
    year_from: int | None = None
    year_to: int | None = None
    sections: tuple[str, ...] = ()
    source_types: tuple[str, ...] = ()
    dois: tuple[str, ...] = ()
    source_urls: tuple[str, ...] = ()
    journals: tuple[str, ...] = ()
    taxa: tuple[str, ...] = ()
    compounds: tuple[str, ...] = ()
    host: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "year_from": self.year_from,
            "year_to": self.year_to,
            "sections": list(self.sections),
            "source_types": list(self.source_types),
            "dois": list(self.dois),
            "source_urls": list(self.source_urls),
            "journals": list(self.journals),
            "taxa": list(self.taxa),
            "compounds": list(self.compounds),
            "host": list(self.host),
        }


@dataclass(frozen=True)
class HybridWeights:
    bm25: float = 0.5
    dense: float = 0.5


@dataclass(frozen=True)
class SearchResult:
    chunk_id: Any
    paper_id: Any
    rank: int
    score: float
    text: str
    section: str
    char_start: int
    char_end: int
    matched_terms: list[str]
    score_components: dict[str, Any]
    paper_title: str
    doi: str | None
    source_url: str | None

    @property
    def trace(self) -> dict[str, Any]:
        source_hash = self.score_components.get("source_hash")
        return {
            "chunk_id": str(self.chunk_id),
            "paper_id": str(self.paper_id),
            "doi": self.doi,
            "source_url": self.source_url,
            "section": self.section,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "source_hash": source_hash,
        }


TextEmbeddingProvider = LiteratureEmbeddingProvider
SearchReranker = LiteratureReranker


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", text)]


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _casefolded(values: Sequence[str]) -> set[str]:
    return {value.casefold() for value in values if value}


def _metadata_values(chunk: PaperChunk, key: str) -> set[str]:
    value = chunk.chunk_metadata.get(key)
    if value is None:
        return set()
    if isinstance(value, str):
        return {value.casefold()}
    if isinstance(value, Sequence):
        return {str(item).casefold() for item in value}
    return {str(value).casefold()}


def _overlaps(left: set[str], right: Sequence[str]) -> bool:
    return not left.isdisjoint(_casefolded(right))


def _passes_filters(chunk: PaperChunk, filters: SearchFilters) -> bool:
    paper = chunk.paper
    if filters.year_from is not None and (paper.year is None or paper.year < filters.year_from):
        return False
    if filters.year_to is not None and (paper.year is None or paper.year > filters.year_to):
        return False
    if filters.sections and chunk.section.casefold() not in {
        section.casefold() for section in filters.sections
    }:
        return False
    if filters.dois and (paper.doi is None or paper.doi.casefold() not in _casefolded(filters.dois)):
        return False
    if filters.source_urls and (
        paper.source_url is None or paper.source_url.casefold() not in _casefolded(filters.source_urls)
    ):
        return False
    if filters.journals and (
        paper.journal is None or paper.journal.casefold() not in _casefolded(filters.journals)
    ):
        return False
    if filters.source_types and not _overlaps(_metadata_values(chunk, "source_type"), filters.source_types):
        return False
    if filters.taxa:
        if not _overlaps(_metadata_values(chunk, "taxa"), filters.taxa):
            return False
    if filters.compounds:
        if not _overlaps(_metadata_values(chunk, "compounds"), filters.compounds):
            return False
    if filters.host:
        if not _overlaps(_metadata_values(chunk, "host"), filters.host):
            return False
    return True


def _filtered_chunks(session: Session, filters: SearchFilters) -> list[PaperChunk]:
    statement = select(PaperChunk).join(Paper).order_by(PaperChunk.created_at)
    if filters.year_from is not None:
        statement = statement.where(Paper.year >= filters.year_from)
    if filters.year_to is not None:
        statement = statement.where(Paper.year <= filters.year_to)
    if filters.sections:
        statement = statement.where(func.lower(PaperChunk.section).in_(_casefolded(filters.sections)))
    if filters.dois:
        statement = statement.where(func.lower(Paper.doi).in_(_casefolded(filters.dois)))
    if filters.source_urls:
        statement = statement.where(func.lower(Paper.source_url).in_(_casefolded(filters.source_urls)))
    if filters.journals:
        statement = statement.where(func.lower(Paper.journal).in_(_casefolded(filters.journals)))

    return [
        chunk
        for chunk in session.scalars(statement)
        if _passes_filters(chunk, filters)
    ]


def _result_from_chunk(
    chunk: PaperChunk,
    *,
    rank: int,
    score: float,
    matched_terms: list[str],
    score_components: dict[str, Any],
) -> SearchResult:
    paper = chunk.paper
    enriched_components = {**score_components, "source_hash": chunk.source_hash}
    return SearchResult(
        chunk_id=chunk.chunk_id,
        paper_id=paper.paper_id,
        rank=rank,
        score=score,
        text=chunk.text,
        section=chunk.section,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        matched_terms=matched_terms,
        score_components=enriched_components,
        paper_title=paper.title,
        doi=paper.doi,
        source_url=paper.source_url,
    )


def _sort_and_rank(results: list[SearchResult], *, top_k: int) -> list[SearchResult]:
    sorted_results = sorted(
        results,
        key=lambda result: (
            -result.score,
            result.paper_title,
            result.section,
            result.char_start,
        ),
    )
    return [
        replace(result, rank=rank)
        for rank, result in enumerate(sorted_results[:top_k], start=1)
    ]


def _normalize_scores(scores: dict[Any, float]) -> dict[Any, float]:
    if not scores:
        return {}
    max_score = max(scores.values())
    if max_score <= 0:
        return {key: 0.0 for key in scores}
    return {key: value / max_score for key, value in scores.items()}


def _dense_chunk_scores(
    chunks: list[PaperChunk],
    query: str,
    provider: TextEmbeddingProvider,
    vector_index: LiteratureVectorIndex | None,
) -> tuple[dict[Any, float], str]:
    if not chunks:
        return {}, vector_index.index_name if vector_index is not None else InMemoryLiteratureVectorIndex.index_name

    chunk_by_key = {str(chunk.chunk_id): chunk for chunk in chunks}
    active_index = vector_index or InMemoryLiteratureVectorIndex.from_chunks(chunks, provider)
    hits = active_index.search(
        provider.embed(query),
        top_k=len(chunks),
        candidate_chunk_ids=set(chunk_by_key),
    )
    return {
        chunk_by_key[hit.chunk_id].chunk_id: hit.score
        for hit in hits
        if hit.chunk_id in chunk_by_key
    }, active_index.index_name


def _bm25_chunk_scores(
    chunks: list[PaperChunk],
    query_terms: list[str],
) -> list[tuple[float, PaperChunk, list[str], dict[str, float]]]:
    if not chunks:
        return []

    documents = [tokenize(chunk.text) for chunk in chunks]
    doc_lengths = [len(document) for document in documents]
    average_doc_length = sum(doc_lengths) / len(doc_lengths)
    document_frequency: Counter[str] = Counter()
    for document in documents:
        document_frequency.update(set(document))

    k1 = 1.5
    b = 0.75
    scored: list[tuple[float, PaperChunk, list[str], dict[str, float]]] = []
    for chunk, document, doc_length in zip(chunks, documents, doc_lengths, strict=True):
        term_frequency = Counter(document)
        matched_terms: list[str] = []
        term_scores: dict[str, float] = {}
        score = 0.0
        for term in query_terms:
            frequency = term_frequency[term]
            if frequency == 0:
                continue
            matched_terms.append(term)
            idf = math.log(
                1
                + (len(documents) - document_frequency[term] + 0.5)
                / (document_frequency[term] + 0.5)
            )
            denominator = frequency + k1 * (1 - b + b * doc_length / average_doc_length)
            term_score = idf * (frequency * (k1 + 1)) / denominator
            term_scores[term] = term_score
            score += term_score
        if score > 0:
            scored.append((score, chunk, sorted(set(matched_terms)), term_scores))
    return scored


def bm25_search(
    session: Session,
    query: str,
    *,
    top_k: int = 10,
    filters: SearchFilters | None = None,
) -> list[SearchResult]:
    resolved_filters = filters or SearchFilters()
    query_terms = tokenize(query)
    if not query_terms or top_k <= 0:
        return []

    chunks = _filtered_chunks(session, resolved_filters)
    if not chunks:
        return []

    results = [
        _result_from_chunk(
            chunk,
            rank=0,
            score=score,
            matched_terms=matched_terms,
            score_components={"bm25": score, "terms": term_scores},
        )
        for score, chunk, matched_terms, term_scores in _bm25_chunk_scores(chunks, query_terms)
    ]
    return _sort_and_rank(results, top_k=top_k)


def dense_search(
    session: Session,
    query: str,
    *,
    top_k: int = 10,
    filters: SearchFilters | None = None,
    embedding_provider: TextEmbeddingProvider | None = None,
    vector_index: LiteratureVectorIndex | None = None,
) -> list[SearchResult]:
    resolved_filters = filters or SearchFilters()
    query_terms = tokenize(query)
    if not query_terms or top_k <= 0:
        return []
    provider = embedding_provider or HashingEmbeddingProvider()
    chunks = _filtered_chunks(session, resolved_filters)
    dense_scores, vector_index_name = _dense_chunk_scores(chunks, query, provider, vector_index)
    chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}

    results: list[SearchResult] = []
    for chunk_id, dense_score in dense_scores.items():
        chunk = chunk_by_id[chunk_id]
        chunk_terms = set(tokenize(chunk.text))
        matched_terms = sorted(set(query_terms).intersection(chunk_terms))
        results.append(
            _result_from_chunk(
                chunk,
                rank=0,
                score=dense_score,
                matched_terms=matched_terms,
                score_components={
                    "dense": dense_score,
                    "embedding_provider": provider.provider_name,
                    "vector_index": vector_index_name,
                },
            )
        )
    return _sort_and_rank(results, top_k=top_k)


def indexed_dense_search(
    session: Session,
    query: str,
    *,
    vector_index: LiteratureVectorIndex,
    top_k: int = 10,
    filters: SearchFilters | None = None,
    embedding_provider: TextEmbeddingProvider | None = None,
) -> list[SearchResult]:
    return dense_search(
        session,
        query,
        top_k=top_k,
        filters=filters,
        embedding_provider=embedding_provider,
        vector_index=vector_index,
    )


def hybrid_search(
    session: Session,
    query: str,
    *,
    top_k: int = 10,
    filters: SearchFilters | None = None,
    embedding_provider: TextEmbeddingProvider | None = None,
    weights: HybridWeights | None = None,
    vector_index: LiteratureVectorIndex | None = None,
) -> list[SearchResult]:
    resolved_filters = filters or SearchFilters()
    query_terms = tokenize(query)
    if not query_terms or top_k <= 0:
        return []

    provider = embedding_provider or HashingEmbeddingProvider()
    resolved_weights = weights or HybridWeights()
    chunks = _filtered_chunks(session, resolved_filters)
    bm25_scored = _bm25_chunk_scores(chunks, query_terms)
    bm25_scores = {chunk.chunk_id: score for score, chunk, _matched, _terms in bm25_scored}
    bm25_terms = {chunk.chunk_id: terms for _score, chunk, _matched, terms in bm25_scored}
    bm25_matched = {chunk.chunk_id: matched for _score, chunk, matched, _terms in bm25_scored}

    dense_scores, vector_index_name = _dense_chunk_scores(chunks, query, provider, vector_index)

    normalized_bm25 = _normalize_scores(bm25_scores)
    normalized_dense = _normalize_scores(dense_scores)
    chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}

    results: list[SearchResult] = []
    for chunk_id in set(normalized_bm25) | set(normalized_dense):
        chunk = chunk_by_id[chunk_id]
        bm25_component = normalized_bm25.get(chunk_id, 0.0)
        dense_component = normalized_dense.get(chunk_id, 0.0)
        hybrid_score = (
            resolved_weights.bm25 * bm25_component
            + resolved_weights.dense * dense_component
        )
        if hybrid_score <= 0:
            continue
        matched_terms = sorted(
            set(bm25_matched.get(chunk_id, []))
            | set(tokenize(query)).intersection(tokenize(chunk.text))
        )
        results.append(
            _result_from_chunk(
                chunk,
                rank=0,
                score=hybrid_score,
                matched_terms=matched_terms,
                score_components={
                    "bm25": bm25_scores.get(chunk_id, 0.0),
                    "bm25_normalized": bm25_component,
                    "dense": dense_scores.get(chunk_id, 0.0),
                    "dense_normalized": dense_component,
                    "hybrid": hybrid_score,
                    "weights": {
                        "bm25": resolved_weights.bm25,
                        "dense": resolved_weights.dense,
                    },
                    "terms": bm25_terms.get(chunk_id, {}),
                    "embedding_provider": provider.provider_name,
                    "vector_index": vector_index_name,
                },
            )
        )
    return _sort_and_rank(results, top_k=top_k)


def rerank_search_results(
    query: str,
    results: list[SearchResult],
    *,
    reranker: SearchReranker | None = None,
    reranker_weight: float = 1.0,
    top_k: int | None = None,
) -> list[SearchResult]:
    if not results:
        return []
    active_reranker = reranker or create_literature_reranker()
    rerank_scores = active_reranker.score(query, [result.text for result in results])
    if len(rerank_scores) != len(results):
        raise RuntimeError(
            f"Reranker returned {len(rerank_scores)} scores for {len(results)} passages."
        )
    rescored_results: list[SearchResult] = []
    for result, rerank_score in zip(results, rerank_scores, strict=True):
        rescored_results.append(
            replace(
                result,
                score=result.score + reranker_weight * rerank_score,
                score_components={
                    **result.score_components,
                    "pre_rerank_score": result.score,
                    "reranker": rerank_score,
                    "reranker_weight": reranker_weight,
                },
            )
        )
    return _sort_and_rank(rescored_results, top_k=top_k or len(rescored_results))


def search_paper_chunks(
    session: Session,
    query: str,
    *,
    runtime: LiteratureRetrievalRuntime | None = None,
    top_k: int = 10,
    filters: SearchFilters | None = None,
    retrieval_mode: str = "bm25",
    embedding_provider: TextEmbeddingProvider | None = None,
    reranker: SearchReranker | None = None,
    hybrid_weights: HybridWeights | None = None,
    vector_index: LiteratureVectorIndex | None = None,
    reranker_weight: float = 1.0,
) -> list[SearchResult]:
    active_runtime = runtime or get_default_literature_runtime()
    resolved_embedding = embedding_provider or active_runtime.embedding_provider
    resolved_reranker = reranker or active_runtime.reranker
    resolved_vector_index = (
        vector_index if vector_index is not None else active_runtime.vector_index
    )
    if retrieval_mode == "bm25":
        return bm25_search(session, query, top_k=top_k, filters=filters)
    if retrieval_mode == "dense":
        return dense_search(
            session,
            query,
            top_k=top_k,
            filters=filters,
            embedding_provider=resolved_embedding,
            vector_index=resolved_vector_index,
        )
    if retrieval_mode == "hybrid":
        return hybrid_search(
            session,
            query,
            top_k=top_k,
            filters=filters,
            embedding_provider=resolved_embedding,
            weights=hybrid_weights,
            vector_index=resolved_vector_index,
        )
    if retrieval_mode == "hybrid_rerank":
        base_results = hybrid_search(
            session,
            query,
            top_k=max(top_k * 3, top_k),
            filters=filters,
            embedding_provider=resolved_embedding,
            weights=hybrid_weights,
            vector_index=resolved_vector_index,
        )
        return rerank_search_results(
            query,
            base_results,
            reranker=resolved_reranker,
            reranker_weight=reranker_weight,
            top_k=top_k,
        )
    raise ValueError(f"Unsupported retrieval_mode: {retrieval_mode}")


def persist_retrieval_results(
    session: Session,
    *,
    query: str,
    results: list[SearchResult],
    filters: SearchFilters | None = None,
    retrieval_mode: str = "bm25",
    parameters: dict[str, Any] | None = None,
) -> RetrievalRun:
    run = RetrievalRun(
        query=query,
        retrieval_mode=retrieval_mode,
        filters=(filters or SearchFilters()).as_dict(),
        parameters=parameters or {},
    )
    session.add(run)
    session.flush()

    for result in results:
        session.add(
            RetrievalResult(
                run_id=run.run_id,
                chunk_id=result.chunk_id,
                rank=result.rank,
                score=result.score,
                score_components=result.score_components,
                matched_terms=result.matched_terms,
                provenance={"trace": result.trace},
            )
        )
    session.flush()
    return run
