from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rhizonp.writer.models import AnswerStatus
from rhizonp.writer.retrieval_writer import RetrievalGroundedWriterResult


@dataclass(frozen=True)
class WriterEvaluationMetrics:
    citation_ref_validity_rate: float
    citation_provenance_coverage: float
    evidence_trace_completeness: float
    unsupported_claim_rate: float
    abstention_correctness: float | None
    conflict_status_correctness: float | None
    heuristic_faithfulness_pending: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation_ref_validity_rate": self.citation_ref_validity_rate,
            "citation_provenance_coverage": self.citation_provenance_coverage,
            "evidence_trace_completeness": self.evidence_trace_completeness,
            "unsupported_claim_rate": self.unsupported_claim_rate,
            "abstention_correctness": self.abstention_correctness,
            "conflict_status_correctness": self.conflict_status_correctness,
            "heuristic_faithfulness_pending": self.heuristic_faithfulness_pending,
            "human_faithfulness_pending": True,
        }


def evaluate_retrieval_grounded_writer_result(
    result: RetrievalGroundedWriterResult,
    *,
    expected_status: AnswerStatus | None = None,
) -> WriterEvaluationMetrics:
    validation = result.citation_validation
    claim_count = len(result.answer.claims)
    unsupported_rate = (
        validation.unsupported_claim_count / claim_count if claim_count else 0.0
    )
    abstention_correctness = None
    if expected_status is not None:
        abstention_correctness = 1.0 if result.answer.status == expected_status else 0.0
    return WriterEvaluationMetrics(
        citation_ref_validity_rate=validation.citation_ref_validity_rate,
        citation_provenance_coverage=validation.citation_provenance_coverage,
        evidence_trace_completeness=validation.evidence_trace_completeness,
        unsupported_claim_rate=round(unsupported_rate, 4),
        abstention_correctness=abstention_correctness,
        conflict_status_correctness=None,
    )


def summarize_writer_results(results: list[RetrievalGroundedWriterResult]) -> dict[str, Any]:
    if not results:
        return {"result_count": 0}
    metrics = [evaluate_retrieval_grounded_writer_result(item) for item in results]
    return {
        "result_count": len(results),
        "citation_ref_validity_rate_mean": round(
            sum(item.citation_ref_validity_rate for item in metrics) / len(metrics),
            4,
        ),
        "citation_provenance_coverage_mean": round(
            sum(item.citation_provenance_coverage for item in metrics) / len(metrics),
            4,
        ),
        "evidence_trace_completeness_mean": round(
            sum(item.evidence_trace_completeness for item in metrics) / len(metrics),
            4,
        ),
        "unsupported_claim_rate_mean": round(
            sum(item.unsupported_claim_rate for item in metrics) / len(metrics),
            4,
        ),
        "heuristic_faithfulness_pending": True,
        "human_faithfulness_pending": True,
    }
