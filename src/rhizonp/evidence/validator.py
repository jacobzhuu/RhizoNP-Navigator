from __future__ import annotations

import re
from typing import Any

from rhizonp.evidence.models import (
    ConstraintId,
    ConstraintValidationContext,
    ConstraintValidationReport,
    ScientificConstraintDecision,
)
from rhizonp.taxonomy.policy import max_supported_claim, tier_allows_strain_claim
from rhizonp.writer.claim_safety import (
    ForbiddenClaimReport,
    check_forbidden_claim_patterns,
    classify_overclaim_violations,
)
from rhizonp.writer.fallback_writer import _detect_conflicts
from rhizonp.writer.models import AnswerStatus, GroundedAnswer, WriterRequest

_TAXONOMY_CONSTRAINTS = frozenset({ConstraintId.GENUS_OBSERVATION_NO_STRAIN_PRODUCTION})
_CHEMICAL_CONSTRAINTS = frozenset({ConstraintId.UNKNOWN_FEATURE_NO_COMPOUND_CONFIRMATION})
_CAUSALITY_CONSTRAINTS = frozenset({ConstraintId.CORRELATION_NO_CAUSATION})
_RETRIEVAL_CONSTRAINTS = frozenset({ConstraintId.MENTION_NO_PRODUCTION})
_PROVENANCE_CONSTRAINTS = frozenset(
    {
        ConstraintId.MISSING_PROVENANCE_LIMITS_CLAIM,
        ConstraintId.FIXTURE_NO_REAL_SOURCE_CLAIM,
    }
)

_FEATURE_LABEL_PATTERN = re.compile(r"^feature[_-]", re.IGNORECASE)


def _grounded_answer_from_context(
    context: ConstraintValidationContext,
) -> GroundedAnswer | None:
    payload = context.grounded_answer
    if not payload:
        return None
    return GroundedAnswer.model_validate(payload)


def _writer_request_from_context(context: ConstraintValidationContext) -> WriterRequest | None:
    payload = context.writer_request
    if not payload:
        return None
    return WriterRequest.model_validate(payload)


def _max_supported_claim(context: ConstraintValidationContext) -> str | None:
    grading = context.taxonomy_grading or {}
    if grading.get("max_supported_claim"):
        return str(grading["max_supported_claim"])
    tier = _evidence_tier(context)
    if tier:
        return max_supported_claim(tier)
    return None


def _evidence_tier(context: ConstraintValidationContext) -> str | None:
    grading = context.taxonomy_grading or {}
    if grading.get("evidence_tier"):
        return str(grading["evidence_tier"])
    candidate = context.candidate_row or {}
    if candidate.get("evidence_tier"):
        return str(candidate["evidence_tier"])
    return None


def _answer_status(context: ConstraintValidationContext) -> str | None:
    answer = context.grounded_answer or {}
    status = answer.get("status")
    return str(status) if status else None


def _collect_output_text(context: ConstraintValidationContext) -> str:
    answer = context.grounded_answer or {}
    parts = [str(answer.get("answer") or "")]
    for claim in answer.get("claims") or []:
        parts.append(str(claim.get("text") or ""))
    return "\n".join(parts)


def _evidence_items(context: ConstraintValidationContext) -> list[dict[str, Any]]:
    request = context.writer_request or {}
    items = request.get("evidence_items") or []
    if items:
        return list(items)
    grounded = context.grounded_answer or {}
    nested = grounded.get("evidence_items")
    if isinstance(nested, list):
        return nested
    return []


def _predicates(context: ConstraintValidationContext) -> list[str]:
    return [str(item.get("predicate") or "").upper() for item in _evidence_items(context)]


def _limitations_text(context: ConstraintValidationContext) -> str:
    return "\n".join(context.limitations).lower()


def _decision(
    constraint_id: ConstraintId,
    *,
    passed: bool,
    violation: str | None,
    source_context: str,
    allowed_claim_level: str | None = None,
    requires_abstention: bool = False,
    required_warning: str | None = None,
    required_limitation: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> ScientificConstraintDecision:
    return ScientificConstraintDecision(
        constraint_id=constraint_id.value,
        passed=passed,
        severity="error" if not passed else "info",
        violation=violation,
        allowed_claim_level=allowed_claim_level,
        requires_abstention=requires_abstention,
        required_warning=required_warning,
        required_limitation=required_limitation,
        source_context=source_context,
        provenance=dict(provenance or {}),
    )


def _check_genus_observation_no_strain_production(
    context: ConstraintValidationContext,
) -> ScientificConstraintDecision:
    max_claim = _max_supported_claim(context)
    tier = _evidence_tier(context)
    status = _answer_status(context)
    answer = _grounded_answer_from_context(context)
    violations: list[str] = []

    if max_claim in {"genus_level_candidate", "retrieval_clue_only"} and status == AnswerStatus.SUPPORTED.value:
        violations.append(
            "Grounded answer is SUPPORTED while taxonomy max_supported_claim only allows candidate-level claims."
        )

    if tier and not tier_allows_strain_claim(tier) and status == AnswerStatus.SUPPORTED.value:
        violations.append(
            f"Grounded answer is SUPPORTED at evidence tier {tier}, which cannot support strain claims."
        )

    if answer is not None:
        overclaim = classify_overclaim_violations(answer).get("taxonomy_overclaim", ForbiddenClaimReport())
        violations.extend(overclaim.violations)

    grading = context.taxonomy_grading or {}
    for warning in grading.get("warnings") or []:
        if "strain-level production" in str(warning).lower() and status == AnswerStatus.SUPPORTED.value:
            violations.append("Taxonomy warnings forbid strain claims but writer status is SUPPORTED.")

    return _decision(
        ConstraintId.GENUS_OBSERVATION_NO_STRAIN_PRODUCTION,
        passed=not violations,
        violation="; ".join(dict.fromkeys(violations)) or None,
        source_context="taxonomy_grading+grounded_answer",
        allowed_claim_level=max_claim,
        provenance={"max_supported_claim": max_claim, "evidence_tier": tier, "status": status},
    )


def _check_unknown_feature_no_compound_confirmation(
    context: ConstraintValidationContext,
) -> ScientificConstraintDecision:
    query_context = context.query_context or {}
    metabolite_label = str(query_context.get("metabolite_raw_label") or "")
    compound_known = query_context.get("compound_identity_known")
    violations: list[str] = []

    if compound_known is False or _FEATURE_LABEL_PATTERN.match(metabolite_label):
        answer = _grounded_answer_from_context(context)
        if answer is not None:
            report = classify_overclaim_violations(answer).get(
                "chemical_identity_overclaim",
                ForbiddenClaimReport(),
            )
            violations.extend(report.violations)
        for query in (context.literature_retrieval or {}).get("queries") or []:
            query_text = str(query.get("query_text") or "")
            if metabolite_label and metabolite_label in query_text:
                violations.append(
                    f"Unknown feature `{metabolite_label}` appears in literature query text."
                )

    passed = not violations
    if compound_known is not False and not _FEATURE_LABEL_PATTERN.match(metabolite_label):
        passed = True

    return _decision(
        ConstraintId.UNKNOWN_FEATURE_NO_COMPOUND_CONFIRMATION,
        passed=passed,
        violation="; ".join(dict.fromkeys(violations)) or None,
        source_context="query_context+literature_retrieval+grounded_answer",
        allowed_claim_level="unknown_feature",
        provenance={
            "metabolite_raw_label": metabolite_label,
            "compound_identity_known": compound_known,
        },
    )


def _check_correlation_no_causation(context: ConstraintValidationContext) -> ScientificConstraintDecision:
    limitations = _limitations_text(context)
    method = (context.association_method or "").lower()
    correlation_context = (
        "correlation" in limitations
        or "co-occurrence" in limitations
        or "correlates" in method
        or "spls" in method
        or "spearman" in method
    )
    violations: list[str] = []
    answer = _grounded_answer_from_context(context)
    if correlation_context and answer is not None:
        report = classify_overclaim_violations(answer).get("causality_overclaim", ForbiddenClaimReport())
        violations.extend(report.violations)
        if "correlation" not in limitations and "co-occurrence" not in limitations:
            violations.append("Missing required correlation/causation limitation disclaimer.")

    passed = not violations if correlation_context else True
    return _decision(
        ConstraintId.CORRELATION_NO_CAUSATION,
        passed=passed,
        violation="; ".join(dict.fromkeys(violations)) or None,
        source_context="limitations+association_method+grounded_answer",
        required_limitation="correlation or co-occurrence does not imply causation",
        provenance={"association_method": context.association_method},
    )


def _check_mention_no_production(context: ConstraintValidationContext) -> ScientificConstraintDecision:
    predicates = _predicates(context)
    mention_only = bool(predicates) and all(
        predicate in {"MENTIONS", "CORRELATES_WITH"} for predicate in predicates
    )
    violations: list[str] = []
    answer = _grounded_answer_from_context(context)
    if mention_only and answer is not None:
        report = classify_overclaim_violations(answer).get(
            "production_overclaim_from_mention",
            ForbiddenClaimReport(),
        )
        violations.extend(report.violations)
        if _answer_status(context) == AnswerStatus.SUPPORTED.value:
            violations.append("Mention-only evidence produced a SUPPORTED answer.")

    passed = not violations if mention_only else True
    return _decision(
        ConstraintId.MENTION_NO_PRODUCTION,
        passed=passed,
        violation="; ".join(dict.fromkeys(violations)) or None,
        source_context="writer_request+grounded_answer",
        allowed_claim_level="retrieval_clue_only",
        provenance={"predicates": predicates},
    )


def _check_candidate_no_confirmation(context: ConstraintValidationContext) -> ScientificConstraintDecision:
    max_claim = _max_supported_claim(context)
    tier = _evidence_tier(context)
    status = _answer_status(context)
    candidate_status = str((context.candidate_row or {}).get("status") or "")
    violations: list[str] = []

    candidate_level = max_claim in {"genus_level_candidate", "retrieval_clue_only"} or tier in {"C", "D"}
    if candidate_level and status == AnswerStatus.SUPPORTED.value:
        violations.append("Writer answer is SUPPORTED for candidate-level evidence only.")

    if candidate_level and candidate_status == AnswerStatus.SUPPORTED.value and tier in {"C", "D"}:
        violations.append("Candidate matrix row is SUPPORTED at tier C/D.")

    answer = _grounded_answer_from_context(context)
    if candidate_level and answer is not None:
        report = check_forbidden_claim_patterns(
            answer,
            ["production is confirmed", "confirmed production in this sample"],
        )
        violations.extend(report.violations)

    return _decision(
        ConstraintId.CANDIDATE_NO_CONFIRMATION,
        passed=not violations,
        violation="; ".join(dict.fromkeys(violations)) or None,
        source_context="taxonomy_grading+candidate_row+grounded_answer",
        allowed_claim_level=max_claim or "genus_level_candidate",
        provenance={"candidate_status": candidate_status, "writer_status": status},
    )


def _check_weak_evidence_requires_abstention(
    context: ConstraintValidationContext,
) -> ScientificConstraintDecision:
    if context.expected_requires_abstention is None:
        return _decision(
            ConstraintId.WEAK_EVIDENCE_REQUIRES_ABSTENTION,
            passed=True,
            violation=None,
            source_context="not_applicable",
        )

    status = _answer_status(context)
    abstained = status == AnswerStatus.INSUFFICIENT_EVIDENCE.value
    passed = abstained if context.expected_requires_abstention else not abstained
    violation = None
    if not passed:
        violation = (
            f"Expected abstention={context.expected_requires_abstention} "
            f"but grounded answer status={status}."
        )
    return _decision(
        ConstraintId.WEAK_EVIDENCE_REQUIRES_ABSTENTION,
        passed=passed,
        violation=violation,
        source_context="grounded_answer",
        requires_abstention=bool(context.expected_requires_abstention),
        provenance={"status": status},
    )


def _check_conflicting_evidence_requires_conflict_status(
    context: ConstraintValidationContext,
) -> ScientificConstraintDecision:
    request = _writer_request_from_context(context)
    has_conflict = False
    if request is not None and request.evidence_items:
        has_conflict = _detect_conflicts(request.evidence_items)

    status = _answer_status(context)
    violations: list[str] = []
    if has_conflict and status != AnswerStatus.CONFLICTING_EVIDENCE.value:
        violations.append(
            f"Conflicting evidence items detected but answer status is {status}."
        )
    if context.expected_requires_conflict and status != AnswerStatus.CONFLICTING_EVIDENCE.value:
        violations.append("Expected CONFLICTING_EVIDENCE status was not produced.")

    if context.expected_requires_conflict is False and status == AnswerStatus.CONFLICTING_EVIDENCE.value:
        violations.append("Unexpected CONFLICTING_EVIDENCE status for unrelated predicates.")

    passed = not violations
    return _decision(
        ConstraintId.CONFLICTING_EVIDENCE_REQUIRES_CONFLICT_STATUS,
        passed=passed,
        violation="; ".join(dict.fromkeys(violations)) or None,
        source_context="writer_request+grounded_answer",
        provenance={"has_conflict": has_conflict, "status": status},
    )


def _check_missing_provenance_limits_claim(
    context: ConstraintValidationContext,
) -> ScientificConstraintDecision:
    validation = context.citation_validation or {}
    missing = int(validation.get("missing_provenance_count") or 0)
    dangling = int(validation.get("dangling_ref_count") or 0)
    status = _answer_status(context)
    violations: list[str] = []
    if missing > 0 and status == AnswerStatus.SUPPORTED.value:
        violations.append(
            f"Citation trace missing provenance for {missing} evidence item(s) while status is SUPPORTED."
        )
    if dangling > 0:
        violations.append(f"Citation trace has {dangling} dangling reference(s).")

    return _decision(
        ConstraintId.MISSING_PROVENANCE_LIMITS_CLAIM,
        passed=not violations,
        violation="; ".join(dict.fromkeys(violations)) or None,
        source_context="citation_validation+grounded_answer",
        required_limitation="citation provenance must be complete for supported claims",
        provenance={"missing_provenance_count": missing, "dangling_ref_count": dangling},
    )


def _check_fixture_no_real_source_claim(context: ConstraintValidationContext) -> ScientificConstraintDecision:
    scope = (context.provenance_scope or "").lower()
    literature = context.literature_retrieval or {}
    status = str(literature.get("status") or "").upper()
    fixture_context = scope in {"fixture_only", "synthetic_fixture"} or status == "FIXTURE_TEST_ONLY"

    hits = literature.get("hits") or []
    if hits and all(hit.get("is_fixture") for hit in hits):
        fixture_context = True

    violations: list[str] = []
    limitations = _limitations_text(context)
    if fixture_context:
        if "fixture" not in limitations and "synthetic" not in limitations:
            violations.append("Fixture corpus used without explicit fixture limitation.")
        answer = _grounded_answer_from_context(context)
        if answer is not None:
            for pattern in ("pubmed-validated", "externally validated", "real-world evidence"):
                report = check_forbidden_claim_patterns(answer, [pattern])
                violations.extend(report.violations)

    passed = not violations if fixture_context else True
    return _decision(
        ConstraintId.FIXTURE_NO_REAL_SOURCE_CLAIM,
        passed=passed,
        violation="; ".join(dict.fromkeys(violations)) or None,
        source_context="literature_retrieval+limitations+grounded_answer",
        required_limitation="fixture/test corpus disclaimer",
        provenance={"provenance_scope": context.provenance_scope, "literature_status": status},
    )


def _check_cross_module_consistency(context: ConstraintValidationContext) -> ScientificConstraintDecision:
    if not context.source_modules or len(context.source_modules) < 2:
        return _decision(
            ConstraintId.CROSS_MODULE_CONSISTENCY,
            passed=True,
            violation=None,
            source_context="insufficient_modules",
        )

    tier = _evidence_tier(context)
    max_claim = _max_supported_claim(context)
    writer_status = _answer_status(context)
    candidate_status = str((context.candidate_row or {}).get("status") or "")
    violations: list[str] = []

    if tier == "C" and candidate_status == AnswerStatus.SUPPORTED.value:
        violations.append("Linking row is SUPPORTED while taxonomy tier is C.")

    if max_claim == "genus_level_candidate":
        if writer_status == AnswerStatus.SUPPORTED.value:
            violations.append("Writer is SUPPORTED while taxonomy allows only genus-level candidate claims.")
        if candidate_status == AnswerStatus.SUPPORTED.value:
            violations.append("Candidate row is SUPPORTED while taxonomy allows only genus-level candidate claims.")

    grading = context.taxonomy_grading or {}
    distance = grading.get("taxonomy_distance")
    if distance == "SAME_GENUS" and tier == "C":
        if writer_status == AnswerStatus.SUPPORTED.value:
            violations.append("Same-genus tier C evidence produced a SUPPORTED writer answer.")

    return _decision(
        ConstraintId.CROSS_MODULE_CONSISTENCY,
        passed=not violations,
        violation="; ".join(dict.fromkeys(violations)) or None,
        source_context="taxonomy+linking+writer",
        allowed_claim_level=max_claim,
        provenance={
            "modules": list(context.source_modules),
            "taxonomy_distance": distance,
            "writer_status": writer_status,
            "candidate_status": candidate_status,
        },
    )


def validate_scientific_constraints(
    context: ConstraintValidationContext,
) -> ConstraintValidationReport:
    decisions = [
        _check_genus_observation_no_strain_production(context),
        _check_unknown_feature_no_compound_confirmation(context),
        _check_correlation_no_causation(context),
        _check_mention_no_production(context),
        _check_candidate_no_confirmation(context),
        _check_weak_evidence_requires_abstention(context),
        _check_conflicting_evidence_requires_conflict_status(context),
        _check_missing_provenance_limits_claim(context),
        _check_fixture_no_real_source_claim(context),
        _check_cross_module_consistency(context),
    ]

    failed = [decision for decision in decisions if not decision.passed]
    issues = [f"{decision.constraint_id}: {decision.violation}" for decision in failed if decision.violation]

    def _rate(ids: frozenset[ConstraintId]) -> float:
        relevant = [decision for decision in decisions if decision.constraint_id in {item.value for item in ids}]
        if not relevant:
            return 1.0
        passed_count = sum(1 for decision in relevant if decision.passed)
        return passed_count / len(relevant)

    abstention_decision = next(
        decision
        for decision in decisions
        if decision.constraint_id == ConstraintId.WEAK_EVIDENCE_REQUIRES_ABSTENTION.value
    )
    abstention_compliance = (
        1.0
        if abstention_decision.passed and context.expected_requires_abstention is not None
        else None
    )

    return ConstraintValidationReport(
        case_id=context.case_id,
        passed=not failed,
        decisions=decisions,
        constraint_consistency_rate=sum(1 for decision in decisions if decision.passed) / len(decisions),
        taxonomy_boundary_violation_rate=1.0 - _rate(_TAXONOMY_CONSTRAINTS),
        chemical_identity_violation_rate=1.0 - _rate(_CHEMICAL_CONSTRAINTS),
        causality_violation_rate=1.0 - _rate(_CAUSALITY_CONSTRAINTS),
        retrieval_semantic_violation_rate=1.0 - _rate(_RETRIEVAL_CONSTRAINTS),
        provenance_violation_rate=1.0 - _rate(_PROVENANCE_CONSTRAINTS),
        required_abstention_compliance=abstention_compliance,
        issues=issues,
    )
