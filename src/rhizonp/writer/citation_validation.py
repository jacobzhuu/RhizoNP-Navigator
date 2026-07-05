from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from rhizonp.writer.models import EvidenceInput, GroundedAnswer


@dataclass(frozen=True)
class CitationValidationReport:
    citation_ref_validity_rate: float
    citation_provenance_coverage: float
    evidence_trace_completeness: float
    unsupported_claim_count: int
    dangling_ref_count: int
    missing_provenance_count: int
    dangling_refs: list[str] = field(default_factory=list)
    missing_provenance: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation_ref_validity_rate": self.citation_ref_validity_rate,
            "citation_provenance_coverage": self.citation_provenance_coverage,
            "evidence_trace_completeness": self.evidence_trace_completeness,
            "unsupported_claim_count": self.unsupported_claim_count,
            "dangling_ref_count": self.dangling_ref_count,
            "missing_provenance_count": self.missing_provenance_count,
            "dangling_refs": list(self.dangling_refs),
            "missing_provenance": list(self.missing_provenance),
            "unsupported_claims": list(self.unsupported_claims),
            "issues": list(self.issues),
            "validation_kind": "structural_citation_validity",
        }


def _trace_complete(provenance: Mapping[str, Any]) -> bool:
    required = ("chunk_id", "paper_id")
    if not all(provenance.get(key) for key in required):
        return False
    return bool(provenance.get("pmid") or provenance.get("doi") or provenance.get("source_url"))


def validate_citation_trace(
    evidence_items: Sequence[EvidenceInput],
    answer: GroundedAnswer,
) -> CitationValidationReport:
    evidence_by_id = {item.evidence_id: item for item in evidence_items}
    dangling_refs: list[str] = []
    missing_provenance: list[str] = []
    unsupported_claims: list[str] = []
    issues: list[str] = []

    total_claim_refs = 0
    valid_claim_refs = 0
    provenance_checked = 0
    provenance_present = 0
    trace_checked = 0
    trace_complete = 0

    for claim in answer.claims:
        if not claim.evidence_refs:
            unsupported_claims.append(claim.text)
            issues.append("Claim has no evidence_refs.")
            continue
        for ref in claim.evidence_refs:
            total_claim_refs += 1
            item = evidence_by_id.get(ref)
            if item is None:
                dangling_refs.append(str(ref))
                issues.append(f"Dangling evidence ref: {ref}")
                continue
            valid_claim_refs += 1
            provenance_checked += 1
            if item.provenance:
                provenance_present += 1
            else:
                missing_provenance.append(str(ref))
                issues.append(f"Evidence ref {ref} missing provenance.")
            trace_checked += 1
            if _trace_complete(item.provenance):
                trace_complete += 1
            else:
                issues.append(f"Evidence ref {ref} missing chunk/paper/source trace.")

    for ref in answer.evidence_refs:
        if ref not in evidence_by_id:
            dangling_refs.append(str(ref))
            issues.append(f"Top-level dangling evidence ref: {ref}")

    validity_rate = (valid_claim_refs / total_claim_refs) if total_claim_refs else 1.0
    provenance_coverage = (provenance_present / provenance_checked) if provenance_checked else 1.0
    trace_completeness = (trace_complete / trace_checked) if trace_checked else 1.0

    return CitationValidationReport(
        citation_ref_validity_rate=round(validity_rate, 4),
        citation_provenance_coverage=round(provenance_coverage, 4),
        evidence_trace_completeness=round(trace_completeness, 4),
        unsupported_claim_count=len(unsupported_claims),
        dangling_ref_count=len(set(dangling_refs)),
        missing_provenance_count=len(set(missing_provenance)),
        dangling_refs=list(dict.fromkeys(dangling_refs)),
        missing_provenance=list(dict.fromkeys(missing_provenance)),
        unsupported_claims=unsupported_claims,
        issues=list(dict.fromkeys(issues)),
    )


def resolve_evidence_trace(item: EvidenceInput) -> dict[str, Any]:
    provenance = dict(item.provenance)
    return {
        "evidence_id": str(item.evidence_id),
        "chunk_id": provenance.get("chunk_id"),
        "paper_id": provenance.get("paper_id"),
        "pmid": provenance.get("pmid"),
        "doi": provenance.get("doi"),
        "source_url": provenance.get("source_url"),
        "corpus_type": provenance.get("corpus_type"),
        "corpus_id": provenance.get("corpus_id"),
        "is_fixture": provenance.get("is_fixture"),
    }
