from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhizonp.config import PROJECT_ROOT
from rhizonp.evaluation.writer_safety_benchmark import (
    evaluate_static_case,
    load_writer_safety_cases,
    run_own_data_feature_m123_dynamic_case,
    run_writer_safety_benchmark,
    write_writer_safety_reports,
)
from rhizonp.writer.claim_safety import check_forbidden_claim_patterns
from rhizonp.writer.models import AnswerStatus, Claim, EvidenceInput, GroundedAnswer, WriterRequest
from rhizonp.writer.service import write_grounded_answer


def test_load_writer_safety_cases_has_minimum_categories() -> None:
    payload = load_writer_safety_cases()
    categories = {case["category"] for case in payload["cases"]}
    assert "must_abstain_empty" in categories
    assert "must_conflict" in categories
    assert "bounded_answer_strong" in categories
    assert payload["disclaimer"]


def test_empty_evidence_case_abstains() -> None:
    payload = load_writer_safety_cases()
    case = next(item for item in payload["cases"] if item["case_id"] == "ABS001")
    result = evaluate_static_case(case)
    assert result.passed
    assert result.actual_status == AnswerStatus.INSUFFICIENT_EVIDENCE.value


def test_mention_only_case_avoids_production_claims() -> None:
    payload = load_writer_safety_cases()
    case = next(item for item in payload["cases"] if item["case_id"] == "ABS003")
    result = evaluate_static_case(case)
    assert result.passed
    assert not result.forbidden_violations


def test_conflict_case_reports_conflicting_evidence() -> None:
    payload = load_writer_safety_cases()
    case = next(item for item in payload["cases"] if item["case_id"] == "CON001")
    result = evaluate_static_case(case)
    assert result.passed
    assert result.actual_status == AnswerStatus.CONFLICTING_EVIDENCE.value


def test_no_false_conflict_on_different_objects() -> None:
    payload = load_writer_safety_cases()
    case = next(item for item in payload["cases"] if item["case_id"] == "CON002")
    result = evaluate_static_case(case)
    assert result.passed
    assert result.actual_status != AnswerStatus.CONFLICTING_EVIDENCE.value


def test_forbidden_claim_checker_detects_pattern() -> None:
    answer = GroundedAnswer(
        status=AnswerStatus.PARTIALLY_SUPPORTED,
        answer="This sample produces rapamycin.",
        claims=[
            Claim(
                text="This sample produces rapamycin.",
                evidence_refs=[],
                claim_level="descriptive",
            )
        ],
        evidence_refs=[],
        limitations=[],
    )
    report = check_forbidden_claim_patterns(answer, ["this sample produces"])
    assert report.violation_count >= 1


def test_genus_case_avoids_strain_claim() -> None:
    payload = load_writer_safety_cases()
    case = next(item for item in payload["cases"] if item["case_id"] == "ABS004")
    result = evaluate_static_case(case)
    assert result.passed


def test_feature_m123_case_avoids_compound_confirmation() -> None:
    payload = load_writer_safety_cases()
    case = next(item for item in payload["cases"] if item["case_id"] == "ABS005")
    result = evaluate_static_case(case)
    assert result.passed


def test_correlation_case_avoids_causality_claim() -> None:
    payload = load_writer_safety_cases()
    case = next(item for item in payload["cases"] if item["case_id"] == "ABS006")
    result = evaluate_static_case(case)
    assert result.passed


def test_fixture_case_preserves_limitations() -> None:
    payload = load_writer_safety_cases()
    case = next(item for item in payload["cases"] if item["case_id"] == "ABS007")
    result = evaluate_static_case(case)
    assert result.passed


def test_citation_validity_case_passes() -> None:
    payload = load_writer_safety_cases()
    case = next(item for item in payload["cases"] if item["case_id"] == "CIT001")
    result = evaluate_static_case(case)
    assert result.passed
    assert result.citation_ref_validity_rate == 1.0


def test_own_data_dynamic_feature_m123_case() -> None:
    result = run_own_data_feature_m123_dynamic_case()
    assert result.passed
    assert result.source_trace.get("target_raw_label") == "Feature_M123"


def test_run_writer_safety_benchmark_generates_report(tmp_path: Path) -> None:
    report = run_writer_safety_benchmark(include_dynamic=False)
    assert report.case_count >= 14
    assert report.must_abstain_accuracy == 1.0
    assert report.must_conflict_accuracy == 1.0
    assert report.human_faithfulness_pending is True
    json_path, md_path = write_writer_safety_reports(report, tmp_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert "deterministic safety/regression benchmark" in md_path.read_text(encoding="utf-8").lower()


@pytest.mark.skipif(
    not (PROJECT_ROOT / "data" / "snapshots" / "pubmed" / "rhizonp_domain_v1" / "corpus.json").is_file(),
    reason="Bounded PubMed snapshot not present.",
)
def test_real_pubmed_dynamic_case_when_snapshot_present() -> None:
    from rhizonp.evaluation.writer_safety_benchmark import run_real_pubmed_dynamic_case

    result = run_real_pubmed_dynamic_case()
    assert result is not None
    assert result.source_trace.get("pmid")
    assert result.passed


def test_manual_writer_api_path_still_supported() -> None:
    answer = write_grounded_answer(
        WriterRequest(
            question="Does this strain produce rapamycin?",
            evidence_items=[
                EvidenceInput(
                    evidence_id=__import__("uuid").uuid4(),
                    claim_type="taxon_produces_compound",
                    predicate="PRODUCES",
                    object_literal="Rapamycin",
                    evidence_tier="A",
                    supporting_span="Synthetic supporting span.",
                )
            ],
        )
    )
    assert answer.status == AnswerStatus.SUPPORTED
