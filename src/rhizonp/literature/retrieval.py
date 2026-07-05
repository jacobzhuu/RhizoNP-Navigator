from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from rhizonp.domain.models import Paper, PaperChunk, RetrievalResult, RetrievalRun


@dataclass(frozen=True)
class SearchFilters:
    year_from: int | None = None
    year_to: int | None = None
    sections: tuple[str, ...] = ()
    taxa: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "year_from": self.year_from,
            "year_to": self.year_to,
            "sections": list(self.sections),
            "taxa": list(self.taxa),
        }


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
        return {
            "chunk_id": str(self.chunk_id),
            "paper_id": str(self.paper_id),
            "doi": self.doi,
            "source_url": self.source_url,
            "section": self.section,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", text)]


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
    if filters.taxa:
        chunk_taxa = {taxon.casefold() for taxon in chunk.chunk_metadata.get("taxa", [])}
        requested_taxa = {taxon.casefold() for taxon in filters.taxa}
        if chunk_taxa.isdisjoint(requested_taxa):
            return False
    return True


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

    chunks = [
        chunk
        for chunk in session.scalars(select(PaperChunk).join(Paper).order_by(PaperChunk.created_at))
        if _passes_filters(chunk, resolved_filters)
    ]
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

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].paper.title,
            item[1].section,
            item[1].paragraph_index,
        )
    )

    results: list[SearchResult] = []
    for rank, (score, chunk, matched_terms, term_scores) in enumerate(scored[:top_k], start=1):
        paper = chunk.paper
        results.append(
            SearchResult(
                chunk_id=chunk.chunk_id,
                paper_id=paper.paper_id,
                rank=rank,
                score=score,
                text=chunk.text,
                section=chunk.section,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                matched_terms=matched_terms,
                score_components={"bm25": score, "terms": term_scores},
                paper_title=paper.title,
                doi=paper.doi,
                source_url=paper.source_url,
            )
        )
    return results


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
