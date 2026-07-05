#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded live DeepSeek writer evaluation.")
    parser.add_argument(
        "--provider",
        default="deepseek",
        help="Provider label for reporting (default: deepseek).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "reports" / "latest",
        help="Report output directory.",
    )
    return parser.parse_args()


def _evidence_item(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "evidence_id": str(uuid.uuid4()),
        "claim_type": "association",
        "predicate": "MENTIONS",
        "object_literal": "Feature_M123",
        "evidence_tier": "C",
        "directness": "indirect",
        "confidence": 0.5,
        "supporting_span": "Literature mentions Streptomyces and secondary metabolites.",
        "warnings": ["Genus-level observation cannot support strain-level production claims."],
        "provenance": {"pmid": "42348782", "chunk_id": "chunk-1", "paper_id": "paper-1"},
    }
    payload.update(overrides)
    return payload


def _build_cases() -> list[dict[str, object]]:
    mention_id = str(uuid.uuid4())
    conflict_support = str(uuid.uuid4())
    conflict_refute = str(uuid.uuid4())
    return [
        {
            "case_id": "A_real_bounded_pubmed_mention",
            "request": {
                "question": "What does literature mention about Streptomyces metabolites?",
                "evidence_items": [_evidence_item(evidence_id=mention_id)],
                "taxonomy_warnings": ["Genus-level observation cannot support strain-level production claims."],
                "limitations": ["Co-occurrence does not imply production."],
            },
        },
        {
            "case_id": "B_own_data_streptomyces_feature_m123",
            "request": {
                "question": "What literature relates Streptomyces to Feature_M123?",
                "evidence_items": [
                    _evidence_item(
                        evidence_id=str(uuid.uuid4()),
                        object_literal="Feature_M123",
                        supporting_span="Metabolite feature Feature_M123 co-occurs with Streptomyces in literature.",
                    )
                ],
                "taxonomy_warnings": ["Feature_M123 is not structure-confirmed."],
                "limitations": ["Correlation is not causation.", "Unknown chemical identity preserved."],
            },
        },
        {
            "case_id": "C_npatlas_candidate",
            "request": {
                "question": "Is there candidate evidence for a natural product link?",
                "evidence_items": [
                    _evidence_item(
                        evidence_id=str(uuid.uuid4()),
                        claim_type="candidate_link",
                        predicate="MENTIONS",
                        object_literal="rapamycin",
                        evidence_tier="C",
                    )
                ],
                "limitations": ["Candidate evidence is not confirmation."],
            },
        },
        {
            "case_id": "D_conflict",
            "request": {
                "question": "Does evidence support or refute production?",
                "evidence_items": [
                    _evidence_item(
                        evidence_id=conflict_support,
                        predicate="PRODUCES",
                        object_literal="Rapamycin",
                    ),
                    _evidence_item(
                        evidence_id=conflict_refute,
                        predicate="DOES_NOT_PRODUCE",
                        object_literal="Rapamycin",
                    ),
                ],
                "limitations": ["Conflicting evidence requires conservative handling."],
            },
        },
        {
            "case_id": "E_insufficient_evidence",
            "request": {
                "question": "Can we confirm strain-level production?",
                "evidence_items": [],
                "limitations": ["No evidence supplied."],
            },
        },
    ]


def main() -> None:
    from rhizonp.config import get_settings
    from rhizonp.writer.llm_writer import check_llm_configuration, write_deepseek_answer
    from rhizonp.writer.models import WriterRequest

    args = parse_args()
    config = check_llm_configuration()
    settings = get_settings()

    report: dict[str, object] = {
        "validation_type": "deepseek_live_writer_eval",
        "provider": args.provider,
        "model": settings.llm_model,
        "base_url": settings.llm_api_base,
        "config": config,
        "remote_execution": False,
        "cases": [],
    }

    if not config["live_evaluation_ready"]:
        report["status"] = "BLOCKED_BY_EXTERNAL_INPUT: DEEPSEEK_API_KEY_REQUIRED"
        output_path = args.output_dir / "deepseek_live_writer_eval.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print("\nREADY_FOR_USER_CONFIGURATION — fill DEEPSEEK_API_KEY in local .env")
        raise SystemExit(2)

    case_results: list[dict[str, object]] = []
    successful_calls = 0
    schema_valid = 0
    citation_valid = 0
    constraint_compliant = 0
    fallback_count = 0

    for case in _build_cases():
        request = WriterRequest.model_validate(case["request"])
        result = write_deepseek_answer(request, allow_remote=True)
        case_payload = {
            "case_id": case["case_id"],
            "writer_mode": result.writer_mode,
            "status": result.answer.status.value,
            "issues": list(result.issues),
            "citation_ref_validity_rate": result.citation_validation.citation_ref_validity_rate,
            "constraint_passed": (
                result.constraint_report.passed if result.constraint_report is not None else None
            ),
        }
        case_results.append(case_payload)
        if result.writer_mode == "deepseek_applied":
            successful_calls += 1
            schema_valid += 1
        if result.citation_validation.citation_ref_validity_rate == 1.0:
            citation_valid += 1
        if result.constraint_report is not None and result.constraint_report.passed:
            constraint_compliant += 1
        if result.writer_mode.startswith("fallback"):
            fallback_count += 1

    report.update(
        {
            "status": "LIVE_BOUNDED_VALIDATION_COMPLETE",
            "remote_execution": True,
            "case_count": len(case_results),
            "successful_calls": successful_calls,
            "schema_validity_rate": schema_valid / len(case_results) if case_results else 0.0,
            "citation_validity_rate": citation_valid / len(case_results) if case_results else 0.0,
            "constraint_compliance_rate": constraint_compliant / len(case_results) if case_results else 0.0,
            "fallback_rate": fallback_count / len(case_results) if case_results else 0.0,
            "cases": case_results,
            "limitations": [
                "Bounded live execution only; human faithfulness remains pending.",
                "Scientific correctness is not proven by provider success alone.",
            ],
        }
    )

    output_path = args.output_dir / "deepseek_live_writer_eval.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
