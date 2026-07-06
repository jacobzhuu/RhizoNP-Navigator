from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rhizonp.domain.models import Paper, PaperChunk
from rhizonp.literature.retrieval import HybridWeights, SearchResult, search_paper_chunks
from rhizonp.omics.corpus_provenance import CorpusType, classify_paper
from rhizonp.omics.query_builder import (
    GeneratedQuery,
    QueryConstructionContext,
    build_literature_queries,
)
from rhizonp.taxonomy.grading import EvidenceGradingResult, grade_evidence


class LiteratureRetrievalStatus(str, Enum):
    DISABLED = "DISABLED"
    RETRIEVED = "RETRIEVED"
    NO_RESULTS = "NO_RESULTS"
    RETRIEVAL_UNAVAILABLE = "RETRIEVAL_UNAVAILABLE"
    FIXTURE_TEST_ONLY = "FIXTURE_TEST_ONLY"


@dataclass(frozen=True)
class LiteratureEvidenceHit:
    query_text: str
    query_index: int
    paper_id: str
    chunk_id: str
    title: str
    supporting_text: str
    pmid: str | None
    doi: str | None
    source_url: str | None
    journal: str | None
    year: int | None
    section: str
    retrieval_mode: str
    retrieval_score: float
    matched_terms: list[str]
    provenance: dict[str, Any]
    source_type: str
    is_fixture: bool
    taxonomy_grading: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_text": self.query_text,
            "query_index": self.query_index,
            "paper_id": self.paper_id,
            "chunk_id": self.chunk_id,
            "title": self.title,
            "supporting_text": self.supporting_text,
            "pmid": self.pmid,
            "doi": self.doi,
            "source_url": self.source_url,
            "journal": self.journal,
            "year": self.year,
            "section": self.section,
            "retrieval_mode": self.retrieval_mode,
            "retrieval_score": self.retrieval_score,
            "matched_terms": list(self.matched_terms),
            "provenance": dict(self.provenance),
            "source_type": self.source_type,
            "is_fixture": self.is_fixture,
            "taxonomy_grading": self.taxonomy_grading,
        }


@dataclass(frozen=True)
class LiteratureRetrievalResult:
    status: LiteratureRetrievalStatus
    reason: str | None
    queries: list[dict[str, Any]]
    hits: list[LiteratureEvidenceHit]
    retrieval_mode: str
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "queries": list(self.queries),
            "hits": [hit.to_dict() for hit in self.hits],
            "retrieval_mode": self.retrieval_mode,
            "provenance": dict(self.provenance),
        }


class OwnDataLiteratureRetriever(Protocol):
    def retrieve_for_association(
        self,
        context: QueryConstructionContext,
        *,
        query_taxon: str,
        observation_method: str | None,
    ) -> LiteratureRetrievalResult:
        ...


def _paper_is_fixture(paper: Paper | None) -> bool:
    return classify_paper(paper) in {CorpusType.FIXTURE_TEST_ONLY, CorpusType.SYNTHETIC}


def _chunk_source_type(chunk_metadata: dict[str, Any]) -> str:
    source_type = chunk_metadata.get("source_type")
    if isinstance(source_type, str) and source_type:
        return source_type
    return "paper"


def _resolve_literature_taxon(chunk_metadata: dict[str, Any]) -> str | None:
    taxa = chunk_metadata.get("taxa")
    if isinstance(taxa, Sequence) and not isinstance(taxa, str):
        for item in taxa:
            if isinstance(item, str) and item.strip():
                return item.strip()
    if isinstance(taxa, str) and taxa.strip():
        return taxa.strip()
    return None


def _grade_literature_hit_taxonomy(
    query_taxon: str,
    literature_taxon: str | None,
    *,
    observation_method: str | None,
) -> dict[str, Any] | None:
    if not literature_taxon:
        return {
            "status": "unavailable",
            "reason": "No structured taxon metadata on literature chunk.",
        }
    grading: EvidenceGradingResult = grade_evidence(
        query_taxon,
        literature_taxon,
        observation_method=observation_method,
    )
    return {
        "status": "graded",
        "literature_taxon": literature_taxon,
        "grading": grading.to_dict(),
    }


def search_result_to_evidence_hit(
    session: Session,
    result: SearchResult,
    *,
    query_text: str,
    query_index: int,
    retrieval_mode: str,
    query_taxon: str,
    observation_method: str | None,
    chunk_metadata: dict[str, Any] | None = None,
) -> LiteratureEvidenceHit:
    paper = session.get(Paper, result.paper_id)
    metadata = chunk_metadata or {}
    if not metadata:
        chunk = session.get(PaperChunk, result.chunk_id)
        metadata = chunk.chunk_metadata if chunk is not None else {}

    literature_taxon = _resolve_literature_taxon(metadata)
    taxonomy_grading = _grade_literature_hit_taxonomy(
        query_taxon,
        literature_taxon,
        observation_method=observation_method,
    )

    trace = result.trace
    paper_corpus_type = classify_paper(paper)
    return LiteratureEvidenceHit(
        query_text=query_text,
        query_index=query_index,
        paper_id=str(result.paper_id),
        chunk_id=str(result.chunk_id),
        title=result.paper_title,
        supporting_text=result.text,
        pmid=paper.pmid if paper is not None else None,
        doi=result.doi,
        source_url=result.source_url,
        journal=paper.journal if paper is not None else None,
        year=paper.year if paper is not None else None,
        section=result.section,
        retrieval_mode=retrieval_mode,
        retrieval_score=result.score,
        matched_terms=list(result.matched_terms),
        provenance={
            "trace": trace,
            "score_components": dict(result.score_components),
            "association_to_query_to_chunk": True,
            "corpus_type": paper_corpus_type.value,
            "structured_taxa": list(metadata.get("taxa") or []),
            "structured_compounds": list(metadata.get("compounds") or []),
        },
        source_type=_chunk_source_type(metadata),
        is_fixture=_paper_is_fixture(paper),
        taxonomy_grading=taxonomy_grading,
    )


def _session_has_literature_chunks(session: Session) -> bool:
    count = session.scalar(select(func.count()).select_from(PaperChunk))
    return bool(count and count > 0)


def _dedupe_hits(hits: Sequence[LiteratureEvidenceHit]) -> list[LiteratureEvidenceHit]:
    best_by_chunk: dict[str, LiteratureEvidenceHit] = {}
    for hit in hits:
        existing = best_by_chunk.get(hit.chunk_id)
        if existing is None or hit.retrieval_score > existing.retrieval_score:
            best_by_chunk[hit.chunk_id] = hit
    return sorted(
        best_by_chunk.values(),
        key=lambda item: (-item.retrieval_score, item.query_index, item.chunk_id),
    )


@dataclass
class DbBackedLiteratureRetriever:
    """Retrieve literature evidence using the canonical search_paper_chunks stack."""

    session: Session
    retrieval_mode: str = "hybrid_rerank"
    top_k: int = 5
    max_queries: int = 3
    bm25_weight: float = 0.5
    dense_weight: float = 0.5
    reranker_weight: float = 1.0
    corpus_label: str = "db_backed"
    corpus_id: str | None = None
    corpus_type: str | None = None

    def retrieve_for_association(
        self,
        context: QueryConstructionContext,
        *,
        query_taxon: str,
        observation_method: str | None,
    ) -> LiteratureRetrievalResult:
        if not _session_has_literature_chunks(self.session):
            return LiteratureRetrievalResult(
                status=LiteratureRetrievalStatus.RETRIEVAL_UNAVAILABLE,
                reason="DB-backed literature retrieval requires ingested paper chunks.",
                queries=[],
                hits=[],
                retrieval_mode=self.retrieval_mode,
                provenance={
                    "retriever": "DbBackedLiteratureRetriever",
                    "corpus_label": self.corpus_label,
                },
            )

        generated = build_literature_queries(context, max_queries=self.max_queries)
        query_payloads = [
            {
                "query_text": item.query_text,
                "query_index": item.query_index,
                "rationale": item.rationale,
                "query_strength": item.query_strength.value,
                "metabolite_raw_label": context.metabolite_raw_label,
                "compound_identity_known": context.compound_identity_known,
            }
            for item in generated
        ]

        if not generated:
            return LiteratureRetrievalResult(
                status=LiteratureRetrievalStatus.NO_RESULTS,
                reason="No literature queries could be constructed for this association.",
                queries=[],
                hits=[],
                retrieval_mode=self.retrieval_mode,
                provenance={
                    "retriever": "DbBackedLiteratureRetriever",
                    "corpus_label": self.corpus_label,
                },
            )

        collected: list[LiteratureEvidenceHit] = []
        hit_corpus_types: set[CorpusType] = set()
        for generated_query in generated:
            results = search_paper_chunks(
                self.session,
                generated_query.query_text,
                top_k=self.top_k,
                retrieval_mode=self.retrieval_mode,
                hybrid_weights=HybridWeights(
                    bm25=self.bm25_weight,
                    dense=self.dense_weight,
                ),
                reranker_weight=self.reranker_weight,
            )
            for result in results:
                hit = search_result_to_evidence_hit(
                    self.session,
                    result,
                    query_text=generated_query.query_text,
                    query_index=generated_query.query_index,
                    retrieval_mode=self.retrieval_mode,
                    query_taxon=query_taxon,
                    observation_method=observation_method,
                )
                hit_corpus_types.add(CorpusType(hit.provenance.get("corpus_type", CorpusType.UNKNOWN.value)))
                collected.append(hit)

        hits = _dedupe_hits(collected)
        if not hits:
            return LiteratureRetrievalResult(
                status=LiteratureRetrievalStatus.NO_RESULTS,
                reason="Literature retrieval returned no matching chunks.",
                queries=query_payloads,
                hits=[],
                retrieval_mode=self.retrieval_mode,
                provenance={
                    "retriever": "DbBackedLiteratureRetriever",
                    "corpus_label": self.corpus_label,
                    "corpus_id": self.corpus_id,
                    "corpus_type": self.corpus_type,
                    "compound_identity_known": context.compound_identity_known,
                },
            )

        resolved_corpus_type = self.corpus_type
        if resolved_corpus_type is None and len(hit_corpus_types) == 1:
            resolved_corpus_type = next(iter(hit_corpus_types)).value

        if hit_corpus_types and hit_corpus_types <= {
            CorpusType.FIXTURE_TEST_ONLY,
            CorpusType.SYNTHETIC,
        }:
            status = LiteratureRetrievalStatus.FIXTURE_TEST_ONLY
        else:
            status = LiteratureRetrievalStatus.RETRIEVED

        return LiteratureRetrievalResult(
            status=status,
            reason=None,
            queries=query_payloads,
            hits=hits,
            retrieval_mode=self.retrieval_mode,
            provenance={
                "retriever": "DbBackedLiteratureRetriever",
                "corpus_label": self.corpus_label,
                "corpus_id": self.corpus_id,
                "corpus_type": resolved_corpus_type,
                "canonical_search": "rhizonp.literature.retrieval.search_paper_chunks",
                "hit_count": len(hits),
            },
        )


@dataclass
class FixtureTestLiteratureRetriever:
    """Explicit test-only retriever; must not be presented as real external evidence."""

    hits: list[LiteratureEvidenceHit]
    queries: list[GeneratedQuery] = field(default_factory=list)

    def retrieve_for_association(
        self,
        context: QueryConstructionContext,
        *,
        query_taxon: str,
        observation_method: str | None,
    ) -> LiteratureRetrievalResult:
        _ = query_taxon, observation_method, context
        query_payloads = [
            {
                "query_text": item.query_text,
                "query_index": item.query_index,
                "rationale": item.rationale,
                "query_strength": item.query_strength.value,
            }
            for item in self.queries
        ]
        return LiteratureRetrievalResult(
            status=LiteratureRetrievalStatus.FIXTURE_TEST_ONLY,
            reason="Injected fixture test retriever.",
            queries=query_payloads,
            hits=list(self.hits),
            retrieval_mode="fixture_test",
            provenance={"retriever": "FixtureTestLiteratureRetriever"},
        )


def retrieve_literature_for_association(
    context: QueryConstructionContext,
    *,
    query_taxon: str,
    observation_method: str | None,
    enabled: bool,
    session: Session | None = None,
    retriever: OwnDataLiteratureRetriever | None = None,
    retrieval_mode: str = "hybrid_rerank",
    top_k: int = 5,
    max_queries: int = 3,
    corpus_id: str | None = None,
    corpus_type: str | None = None,
) -> LiteratureRetrievalResult:
    if not enabled:
        return LiteratureRetrievalResult(
            status=LiteratureRetrievalStatus.DISABLED,
            reason="Literature retrieval is disabled for this pipeline run.",
            queries=[],
            hits=[],
            retrieval_mode=retrieval_mode,
            provenance={"bridge": "rhizonp.omics.literature_bridge"},
        )

    if retriever is not None:
        return retriever.retrieve_for_association(
            context,
            query_taxon=query_taxon,
            observation_method=observation_method,
        )

    if session is None:
        return LiteratureRetrievalResult(
            status=LiteratureRetrievalStatus.RETRIEVAL_UNAVAILABLE,
            reason="DB-backed literature retrieval is not available (no database session).",
            queries=[],
            hits=[],
            retrieval_mode=retrieval_mode,
            provenance={"bridge": "rhizonp.omics.literature_bridge"},
        )

    active = DbBackedLiteratureRetriever(
        session=session,
        retrieval_mode=retrieval_mode,
        top_k=top_k,
        max_queries=max_queries,
        corpus_id=corpus_id,
        corpus_type=corpus_type,
    )
    return active.retrieve_for_association(
        context,
        query_taxon=query_taxon,
        observation_method=observation_method,
    )
