from __future__ import annotations

import uuid

import pytest

from rhizonp.evaluation.scientific_constraint_benchmark import run_scientific_constraint_benchmark
from rhizonp.evidence.context import (
    build_conflict_context,
    build_empty_evidence_abstention_context,
    build_genus_rapamycin_cross_module_context,
    build_no_false_conflict_context,
    build_npatlas_candidate_context,
)
from rhizonp.evidence.models import ConstraintId
from rhizonp.evidence.validator import validate_scientific_constraints
from rhizonp.writer.fallback_writer import write_fallback_answer
from rhizonp.writer.models import EvidenceInput, GroundedAnswer, WriterRequest


def test_genus_cross_module_case_passes_constraints() -> None:
    context = build_genus_rapamycin_cross_module_context()
    report = validate_scientific_constraints(context)
    assert report.passed
    genus_decision = next(
        decision
        for decision in report.decisions
        if decision.constraint_id == ConstraintId.GENUS_OBSERVATION_NO_STRAIN_PRODUCTION.value
    )
    assert genus_decision.passed
    cross_module = next(
        decision
        for decision in report.decisions
        if decision.constraint_id == ConstraintId.CROSS_MODULE_CONSISTENCY.value
    )
    assert cross_module.passed


def test_empty_evidence_requires_abstention() -> None:
    report = validate_scientific_constraints(build_empty_evidence_abstention_context())
    abstention = next(
        decision
        for decision in report.decisions
        if decision.constraint_id == ConstraintId.WEAK_EVIDENCE_REQUIRES_ABSTENTION.value
    )
    assert abstention.passed
    assert report.passed


def test_explicit_conflict_requires_conflict_status() -> None:
    report = validate_scientific_constraints(build_conflict_context())
    conflict = next(
        decision
        for decision in report.decisions
        if decision.constraint_id == ConstraintId.CONFLICTING_EVIDENCE_REQUIRES_CONFLICT_STATUS.value
    )
    assert conflict.passed


def test_unrelated_opposite_predicates_do_not_force_conflict() -> None:
    report = validate_scientific_constraints(build_no_false_conflict_context())
    conflict = next(
        decision
        for decision in report.decisions
        if decision.constraint_id == ConstraintId.CONFLICTING_EVIDENCE_REQUIRES_CONFLICT_STATUS.value
    )
    assert conflict.passed


def test_mention_only_writer_output_avoids_production_claim() -> None:
    context = build_genus_rapamycin_cross_module_context()
    report = validate_scientific_constraints(context)
    mention = next(
        decision
        for decision in report.decisions
        if decision.constraint_id == ConstraintId.MENTION_NO_PRODUCTION.value
    )
    assert mention.passed


def test_npatlas_candidate_case_avoids_confirmation() -> None:
    report = validate_scientific_constraints(build_npatlas_candidate_context())
    candidate = next(
        decision
        for decision in report.decisions
        if decision.constraint_id == ConstraintId.CANDIDATE_NO_CONFIRMATION.value
    )
    assert candidate.passed


def test_validator_detects_strain_overclaim_violation() -> None:
    from rhizonp.evidence.models import ConstraintValidationContext
    from rhizonp.writer.models import Claim

    bad_answer = GroundedAnswer(
        status="SUPPORTED",
        answer="This sample produces rapamycin via the detected strain.",
        claims=[
            Claim(
                text="The detected strain produces rapamycin in this sample.",
                evidence_refs=[],
                claim_level="descriptive",
            )
        ],
        evidence_refs=[],
        limitations=[],
    )
    context = ConstraintValidationContext(
        case_id="NEG_STRAIN",
        taxonomy_grading={
            "max_supported_claim": "genus_level_candidate",
            "evidence_tier": "C",
            "taxonomy_distance": "SAME_GENUS",
            "warnings": ["Genus-level observation cannot support strain-level production claims."],
        },
        grounded_answer=bad_answer.model_dump(mode="json"),
        source_modules=["taxonomy", "writer"],
    )
    report = validate_scientific_constraints(context)
    genus = next(
        decision
        for decision in report.decisions
        if decision.constraint_id == ConstraintId.GENUS_OBSERVATION_NO_STRAIN_PRODUCTION.value
    )
    assert not genus.passed


def test_own_data_feature_m123_cross_module_case() -> None:
    report = validate_scientific_constraints(
        __import__(
            "rhizonp.evidence.context",
            fromlist=["build_own_data_feature_m123_context"],
        ).build_own_data_feature_m123_context()
    )
    chemical = next(
        decision
        for decision in report.decisions
        if decision.constraint_id == ConstraintId.UNKNOWN_FEATURE_NO_COMPOUND_CONFIRMATION.value
    )
    assert chemical.passed
    correlation = next(
        decision
        for decision in report.decisions
        if decision.constraint_id == ConstraintId.CORRELATION_NO_CAUSATION.value
    )
    assert correlation.passed


def test_real_bounded_pubmed_case_passes_retrieval_semantics() -> None:
    from rhizonp.evidence.context import build_real_bounded_pubmed_context
    from rhizonp.omics.real_pubmed_validation import DEFAULT_SNAPSHOT_DIR

    if not (DEFAULT_SNAPSHOT_DIR / "corpus.json").is_file():
        pytest.skip("Bounded PubMed snapshot not present locally.")
    report = validate_scientific_constraints(build_real_bounded_pubmed_context())
    mention = next(
        decision
        for decision in report.decisions
        if decision.constraint_id == ConstraintId.MENTION_NO_PRODUCTION.value
    )
    assert mention.passed


def test_scientific_constraint_benchmark_passes() -> None:
    report = run_scientific_constraint_benchmark(include_dynamic=True)
    assert report.passed


def test_benchmark_report_scope_wording() -> None:
    report = run_scientific_constraint_benchmark(include_dynamic=False)
    assert "human scientific validation" in report.disclaimer.lower()


def test_correlation_limitation_required_for_pipeline_context() -> None:
    from rhizonp.evidence.models import ConstraintValidationContext

    answer = write_fallback_answer(
        WriterRequest(
            question="Test",
            evidence_items=[
                EvidenceInput(
                    evidence_id=uuid.uuid4(),
                    claim_type="association",
                    predicate="CORRELATES_WITH",
                    object_literal="Feature_M123",
                    evidence_tier="C",
                )
            ],
            limitations=[],
        )
    )
    context = ConstraintValidationContext(
        case_id="NEG_CORR",
        grounded_answer=answer.model_dump(mode="json"),
        association_method="sPLS",
        limitations=[],
    )
    report = validate_scientific_constraints(context)
    correlation = next(
        decision
        for decision in report.decisions
        if decision.constraint_id == ConstraintId.CORRELATION_NO_CAUSATION.value
    )
    assert not correlation.passed
