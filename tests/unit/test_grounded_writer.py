from __future__ import annotations

import uuid

from rhizonp.writer.models import AnswerStatus, EvidenceInput, WriterRequest
from rhizonp.writer.service import write_grounded_answer


def _evidence(
    *,
    tier: str,
    claim_type: str = "taxon_produces_compound",
    predicate: str = "PRODUCES",
    object_literal: str = "Rapamycin",
    warnings: list[str] | None = None,
) -> EvidenceInput:
    return EvidenceInput(
        evidence_id=uuid.uuid4(),
        claim_type=claim_type,
        predicate=predicate,
        object_literal=object_literal,
        evidence_tier=tier,
        directness="direct" if tier == "A" else "indirect",
        confidence=0.9 if tier == "A" else 0.5,
        supporting_span=f"Synthetic supporting span for tier {tier}.",
        taxonomy_distance={"A": "SAME_STRAIN", "B": "SAME_SPECIES", "C": "SAME_GENUS", "D": "UNKNOWN"}[
            tier
        ],
        warnings=warnings or [],
        provenance={"fixture": True},
    )


def test_supported_answer_for_tier_a() -> None:
    request = WriterRequest(
        question="Does this strain produce rapamycin?",
        evidence_items=[_evidence(tier="A")],
    )
    answer = write_grounded_answer(request)
    assert answer.status == AnswerStatus.SUPPORTED
    assert answer.claims
    assert answer.evidence_refs
    assert all(ref in answer.evidence_refs for claim in answer.claims for ref in claim.evidence_refs)


def test_genus_warning_prevents_strain_claim() -> None:
    request = WriterRequest(
        question="Does Streptomyces produce rapamycin?",
        evidence_items=[_evidence(tier="C")],
        taxonomy_warnings=[
            "Genus-level or unresolved observation cannot support strain-level production claims."
        ],
    )
    answer = write_grounded_answer(request)
    assert answer.status == AnswerStatus.PARTIALLY_SUPPORTED
    assert "不支持菌株水平生产" in answer.claims[0].text


def test_insufficient_evidence_when_empty() -> None:
    request = WriterRequest(question="Any evidence?", evidence_items=[])
    answer = write_grounded_answer(request)
    assert answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert not answer.claims


def test_conflicting_evidence_status() -> None:
    support = _evidence(tier="B", predicate="PRODUCES", object_literal="Rapamycin")
    conflict = _evidence(tier="B", predicate="DOES_NOT_PRODUCE", object_literal="Rapamycin")
    request = WriterRequest(
        question="Does the taxon produce rapamycin?",
        evidence_items=[support, conflict],
    )
    answer = write_grounded_answer(request)
    assert answer.status == AnswerStatus.CONFLICTING_EVIDENCE


def test_limitations_include_causality_guardrail() -> None:
    request = WriterRequest(
        question="Is there a causal link?",
        evidence_items=[_evidence(tier="C")],
    )
    answer = write_grounded_answer(request)
    assert any("因果" in limitation for limitation in answer.limitations)
