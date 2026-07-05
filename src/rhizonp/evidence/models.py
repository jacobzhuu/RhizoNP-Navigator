from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConstraintId(str, Enum):
    GENUS_OBSERVATION_NO_STRAIN_PRODUCTION = "GENUS_OBSERVATION_NO_STRAIN_PRODUCTION"
    UNKNOWN_FEATURE_NO_COMPOUND_CONFIRMATION = "UNKNOWN_FEATURE_NO_COMPOUND_CONFIRMATION"
    CORRELATION_NO_CAUSATION = "CORRELATION_NO_CAUSATION"
    MENTION_NO_PRODUCTION = "MENTION_NO_PRODUCTION"
    CANDIDATE_NO_CONFIRMATION = "CANDIDATE_NO_CONFIRMATION"
    WEAK_EVIDENCE_REQUIRES_ABSTENTION = "WEAK_EVIDENCE_REQUIRES_ABSTENTION"
    CONFLICTING_EVIDENCE_REQUIRES_CONFLICT_STATUS = (
        "CONFLICTING_EVIDENCE_REQUIRES_CONFLICT_STATUS"
    )
    MISSING_PROVENANCE_LIMITS_CLAIM = "MISSING_PROVENANCE_LIMITS_CLAIM"
    FIXTURE_NO_REAL_SOURCE_CLAIM = "FIXTURE_NO_REAL_SOURCE_CLAIM"
    CROSS_MODULE_CONSISTENCY = "CROSS_MODULE_CONSISTENCY"


@dataclass(frozen=True)
class ScientificConstraintDecision:
    constraint_id: str
    passed: bool
    severity: str
    violation: str | None = None
    allowed_claim_level: str | None = None
    requires_abstention: bool = False
    required_warning: str | None = None
    required_limitation: str | None = None
    source_context: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "passed": self.passed,
            "severity": self.severity,
            "violation": self.violation,
            "allowed_claim_level": self.allowed_claim_level,
            "requires_abstention": self.requires_abstention,
            "required_warning": self.required_warning,
            "required_limitation": self.required_limitation,
            "source_context": self.source_context,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class ConstraintValidationContext:
    case_id: str
    taxonomy_grading: dict[str, Any] | None = None
    query_context: dict[str, Any] | None = None
    candidate_row: dict[str, Any] | None = None
    literature_retrieval: dict[str, Any] | None = None
    writer_request: dict[str, Any] | None = None
    grounded_answer: dict[str, Any] | None = None
    citation_validation: dict[str, Any] | None = None
    limitations: list[str] = field(default_factory=list)
    association_method: str | None = None
    provenance_scope: str | None = None
    expected_requires_abstention: bool | None = None
    expected_requires_conflict: bool | None = None
    source_modules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "taxonomy_grading": dict(self.taxonomy_grading or {}),
            "query_context": dict(self.query_context or {}),
            "candidate_row": dict(self.candidate_row or {}),
            "literature_retrieval": dict(self.literature_retrieval or {}),
            "writer_request": dict(self.writer_request or {}),
            "grounded_answer": dict(self.grounded_answer or {}),
            "citation_validation": dict(self.citation_validation or {}),
            "limitations": list(self.limitations),
            "association_method": self.association_method,
            "provenance_scope": self.provenance_scope,
            "expected_requires_abstention": self.expected_requires_abstention,
            "expected_requires_conflict": self.expected_requires_conflict,
            "source_modules": list(self.source_modules),
        }


@dataclass(frozen=True)
class ConstraintValidationReport:
    case_id: str
    passed: bool
    decisions: list[ScientificConstraintDecision]
    constraint_consistency_rate: float
    taxonomy_boundary_violation_rate: float
    chemical_identity_violation_rate: float
    causality_violation_rate: float
    retrieval_semantic_violation_rate: float
    provenance_violation_rate: float
    required_abstention_compliance: float | None
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "decisions": [decision.to_dict() for decision in self.decisions],
            "constraint_consistency_rate": self.constraint_consistency_rate,
            "taxonomy_boundary_violation_rate": self.taxonomy_boundary_violation_rate,
            "chemical_identity_violation_rate": self.chemical_identity_violation_rate,
            "causality_violation_rate": self.causality_violation_rate,
            "retrieval_semantic_violation_rate": self.retrieval_semantic_violation_rate,
            "provenance_violation_rate": self.provenance_violation_rate,
            "required_abstention_compliance": self.required_abstention_compliance,
            "issues": list(self.issues),
        }
