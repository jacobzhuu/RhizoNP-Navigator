from __future__ import annotations

from collections.abc import Sequence

from rhizonp.taxonomy.policy import tier_allows_species_claim, tier_allows_strain_claim
from rhizonp.writer.models import (
    AnswerStatus,
    Claim,
    EvidenceInput,
    GroundedAnswer,
    WriterRequest,
)


def _tier_rank(tier: str) -> int:
    normalized = tier.upper().replace("TIER ", "")
    return {"A": 4, "B": 3, "C": 2, "D": 1}.get(normalized, 0)


def _detect_conflicts(evidence_items: Sequence[EvidenceInput]) -> bool:
    supports: set[str] = set()
    refutes: set[str] = set()
    for item in evidence_items:
        predicate = item.predicate.upper()
        key = item.object_literal or item.claim_type
        if predicate in {"PRODUCES", "SUPPORTS"}:
            supports.add(key)
        if predicate in {"DOES_NOT_PRODUCE", "REFUTES", "NEGATES"}:
            refutes.add(key)
    return bool(supports & refutes)


def _strongest_tier(evidence_items: Sequence[EvidenceInput]) -> str:
    if not evidence_items:
        return "D"
    return max((item.evidence_tier for item in evidence_items), key=_tier_rank)


def _build_claims(
    request: WriterRequest,
    *,
    allow_strain_claim: bool,
    allow_species_claim: bool,
) -> list[Claim]:
    claims: list[Claim] = []
    for item in request.evidence_items:
        if item.predicate.upper() in {"DOES_NOT_PRODUCE", "REFUTES", "NEGATES"}:
            claims.append(
                Claim(
                    text=(
                        f"Conflicting evidence indicates the proposed relation may not hold "
                        f"for {item.object_literal or 'the target entity'}."
                    ),
                    evidence_refs=[item.evidence_id],
                    claim_level="conflict",
                )
            )
            continue

        if not allow_strain_claim and "strain" in item.claim_type.lower():
            continue

        claim_text = item.supporting_span or (
            f"Evidence ({item.evidence_tier}) supports {item.claim_type.replace('_', ' ')} "
            f"with {item.directness} directness."
        )
        if not allow_strain_claim and tier_allows_strain_claim(item.evidence_tier) is False:
            claim_text = (
                f"Candidate-level evidence ({item.evidence_tier}) relates to "
                f"{item.object_literal or 'a related entity'}; strain-level production is not supported."
            )
        elif not allow_species_claim:
            claim_text = (
                f"Only weak taxonomy evidence ({item.evidence_tier}) is available for "
                f"{item.object_literal or 'the target entity'}."
            )

        claims.append(
            Claim(
                text=claim_text,
                evidence_refs=[item.evidence_id],
                claim_level="descriptive" if allow_species_claim else "candidate",
            )
        )
    return claims


def write_fallback_answer(request: WriterRequest) -> GroundedAnswer:
    if not request.evidence_items:
        return GroundedAnswer(
            status=AnswerStatus.INSUFFICIENT_EVIDENCE,
            answer="Insufficient evidence was found to answer the question conservatively.",
            claims=[],
            evidence_refs=[],
            limitations=list(request.limitations) + ["No evidence items were supplied."],
            suggested_validations=[
                "Expand literature retrieval or add structured database records.",
            ],
            writer_mode="fallback",
            provenance={"writer": "rhizonp.writer.fallback_writer"},
        )

    if _detect_conflicts(request.evidence_items):
        refs = [item.evidence_id for item in request.evidence_items]
        return GroundedAnswer(
            status=AnswerStatus.CONFLICTING_EVIDENCE,
            answer=(
                "Conflicting evidence was found; the system cannot select a single supported conclusion."
            ),
            claims=_build_claims(request, allow_strain_claim=False, allow_species_claim=False),
            evidence_refs=refs,
            limitations=list(request.limitations) + list(request.taxonomy_warnings),
            suggested_validations=["Review primary sources and reconcile conflicting records."],
            writer_mode="fallback",
            provenance={"writer": "rhizonp.writer.fallback_writer"},
        )

    strongest_tier = _strongest_tier(request.evidence_items)
    allow_strain = tier_allows_strain_claim(strongest_tier) and not request.taxonomy_warnings
    allow_species = tier_allows_species_claim(strongest_tier)
    claims = _build_claims(
        request,
        allow_strain_claim=allow_strain,
        allow_species_claim=allow_species,
    )
    refs = [item.evidence_id for item in request.evidence_items]

    limitations = list(dict.fromkeys([*request.limitations, *request.taxonomy_warnings]))
    for item in request.evidence_items:
        limitations.extend(item.warnings)
    limitations = list(dict.fromkeys(limitations))
    limitations.append("Correlation or co-occurrence does not imply biochemical production or causation.")

    if allow_strain:
        status = AnswerStatus.SUPPORTED
        answer = (
            "Supported evidence is available at strain or stronger taxonomy resolution, "
            "with explicit citations attached to each claim."
        )
    elif allow_species:
        status = AnswerStatus.PARTIALLY_SUPPORTED
        answer = (
            "Partially supported evidence is available at species level; strain-level production "
            "should be treated as unverified for the current sample."
        )
    elif _tier_rank(strongest_tier) >= _tier_rank("C"):
        status = AnswerStatus.PARTIALLY_SUPPORTED
        answer = (
            "Only genus-level or weaker candidate evidence is available; conclusions must remain "
            "hypothesis-generating rather than production-confirmed."
        )
    else:
        status = AnswerStatus.INSUFFICIENT_EVIDENCE
        answer = "Available evidence is too weak to support a substantive answer."

    return GroundedAnswer(
        status=status,
        answer=answer,
        claims=claims,
        evidence_refs=refs,
        limitations=limitations,
        suggested_validations=[
            "Validate taxonomy resolution for the query organism.",
            "Confirm metabolite identity with orthogonal analytical methods.",
        ],
        writer_mode="fallback",
        provenance={"writer": "rhizonp.writer.fallback_writer", "strongest_tier": strongest_tier},
    )
