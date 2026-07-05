from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from rhizonp.omics.literature_bridge import LiteratureEvidenceHit, LiteratureRetrievalStatus
from rhizonp.writer.citation_validation import CitationValidationReport, validate_citation_trace
from rhizonp.writer.evidence_adapter import literature_hits_to_evidence_items
from rhizonp.writer.faithfulness import evaluate_claim_faithfulness_diagnostics
from rhizonp.writer.fallback_writer import write_fallback_answer
from rhizonp.writer.models import GroundedAnswer, WriterRequest
from rhizonp.writer.service import write_grounded_answer


@dataclass(frozen=True)
class RetrievalGroundedWriterResult:
    answer: GroundedAnswer
    evidence_items: list[Any]
    citation_validation: CitationValidationReport
    faithfulness_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    retrieval_status: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer.model_dump(mode="json"),
            "evidence_items": [item.model_dump(mode="json") for item in self.evidence_items],
            "citation_validation": self.citation_validation.to_dict(),
            "faithfulness_diagnostics": list(self.faithfulness_diagnostics),
            "retrieval_status": self.retrieval_status,
            "provenance": dict(self.provenance),
        }


def build_writer_request_from_literature_hits(
    question: str,
    hits: Sequence[LiteratureEvidenceHit | Mapping[str, Any]],
    *,
    limitations: list[str] | None = None,
    taxonomy_warnings: list[str] | None = None,
) -> WriterRequest:
    evidence_items = literature_hits_to_evidence_items(hits)
    merged_limitations = [
        "Retrieved literature passages are retrieval clues only; relevance is not guaranteed.",
        "Co-occurrence in text does not imply biochemical production or causation.",
    ]
    if limitations:
        merged_limitations.extend(limitations)
    merged_warnings: list[str] = []
    if taxonomy_warnings:
        merged_warnings.extend(taxonomy_warnings)
    for item in evidence_items:
        merged_warnings.extend(item.warnings)
    return WriterRequest(
        question=question,
        evidence_items=evidence_items,
        taxonomy_warnings=list(dict.fromkeys(merged_warnings)),
        limitations=list(dict.fromkeys(merged_limitations)),
    )


def write_grounded_answer_from_literature_hits(
    question: str,
    hits: Sequence[LiteratureEvidenceHit | Mapping[str, Any]],
    *,
    limitations: list[str] | None = None,
    taxonomy_warnings: list[str] | None = None,
    retrieval_status: str | None = None,
    use_llm: bool = False,
) -> RetrievalGroundedWriterResult:
    if not hits:
        empty_request = WriterRequest(
            question=question,
            evidence_items=[],
            limitations=list(limitations or [])
            + ["No literature retrieval hits were available for writer grounding."],
            taxonomy_warnings=list(taxonomy_warnings or []),
        )
        answer = write_grounded_answer(empty_request, use_llm=use_llm)
        validation = validate_citation_trace([], answer)
        return RetrievalGroundedWriterResult(
            answer=answer,
            evidence_items=[],
            citation_validation=validation,
            retrieval_status=retrieval_status,
            provenance={"writer_input": "literature_retrieval", "hit_count": 0},
        )

    request = build_writer_request_from_literature_hits(
        question,
        hits,
        limitations=limitations,
        taxonomy_warnings=taxonomy_warnings,
    )
    answer = write_grounded_answer(request, use_llm=use_llm)
    validation = validate_citation_trace(request.evidence_items, answer)
    evidence_by_id = {item.evidence_id: item for item in request.evidence_items}
    diagnostics = evaluate_claim_faithfulness_diagnostics(answer.claims, evidence_by_id)
    return RetrievalGroundedWriterResult(
        answer=answer,
        evidence_items=request.evidence_items,
        citation_validation=validation,
        faithfulness_diagnostics=diagnostics,
        retrieval_status=retrieval_status,
        provenance={
            "writer_input": "literature_retrieval",
            "hit_count": len(hits),
            "retrieval_status": retrieval_status,
        },
    )


def write_grounded_answer_from_literature_retrieval(
    question: str,
    literature_retrieval: Mapping[str, Any],
    *,
    limitations: list[str] | None = None,
    taxonomy_warnings: list[str] | None = None,
    use_llm: bool = False,
) -> RetrievalGroundedWriterResult:
    status = str(literature_retrieval.get("status") or "")
    if status in {
        LiteratureRetrievalStatus.DISABLED.value,
        LiteratureRetrievalStatus.RETRIEVAL_UNAVAILABLE.value,
    }:
        empty = WriterRequest(
            question=question,
            evidence_items=[],
            limitations=list(limitations or [])
            + [literature_retrieval.get("reason") or f"Literature retrieval status={status}."],
            taxonomy_warnings=list(taxonomy_warnings or []),
        )
        answer = write_fallback_answer(empty)
        return RetrievalGroundedWriterResult(
            answer=answer,
            evidence_items=[],
            citation_validation=validate_citation_trace([], answer),
            retrieval_status=status,
            provenance={"writer_input": "literature_retrieval", "blocked": True},
        )

    hits = list(literature_retrieval.get("hits") or [])
    return write_grounded_answer_from_literature_hits(
        question,
        hits,
        limitations=limitations,
        taxonomy_warnings=taxonomy_warnings,
        retrieval_status=status,
        use_llm=use_llm,
    )
