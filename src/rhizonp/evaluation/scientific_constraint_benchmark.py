from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rhizonp.config import PROJECT_ROOT
from rhizonp.evidence.context import (
    build_conflict_context,
    build_empty_evidence_abstention_context,
    build_genus_rapamycin_cross_module_context,
    build_ncbi_taxonomy_bounded_context,
    build_no_false_conflict_context,
    build_npatlas_candidate_context,
    build_own_data_feature_m123_context,
    build_real_bounded_pubmed_context,
)
from rhizonp.evidence.models import ConstraintValidationReport
from rhizonp.evidence.validator import validate_scientific_constraints

DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "eval" / "reports" / "latest"

DYNAMIC_BUILDERS = {
    "cross_module_genus_rapamycin": build_genus_rapamycin_cross_module_context,
    "empty_evidence_abstention": build_empty_evidence_abstention_context,
    "explicit_conflict": build_conflict_context,
    "no_false_conflict": build_no_false_conflict_context,
    "npatlas_candidate": build_npatlas_candidate_context,
    "ncbi_taxonomy_bounded": build_ncbi_taxonomy_bounded_context,
    "own_data_feature_m123": build_own_data_feature_m123_context,
    "real_bounded_pubmed": build_real_bounded_pubmed_context,
}


@dataclass(frozen=True)
class ScientificConstraintBenchmarkReport:
    benchmark_id: str
    description: str
    disclaimer: str
    case_count: int
    passed_count: int
    failed_count: int
    constraint_consistency_rate: float
    taxonomy_boundary_violation_rate: float
    chemical_identity_violation_rate: float
    causality_violation_rate: float
    retrieval_semantic_violation_rate: float
    provenance_violation_rate: float
    required_abstention_compliance: float
    case_results: list[ConstraintValidationReport]
    limitations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.failed_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "description": self.description,
            "disclaimer": self.disclaimer,
            "case_count": self.case_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "constraint_consistency_rate": self.constraint_consistency_rate,
            "taxonomy_boundary_violation_rate": self.taxonomy_boundary_violation_rate,
            "chemical_identity_violation_rate": self.chemical_identity_violation_rate,
            "causality_violation_rate": self.causality_violation_rate,
            "retrieval_semantic_violation_rate": self.retrieval_semantic_violation_rate,
            "provenance_violation_rate": self.provenance_violation_rate,
            "required_abstention_compliance": self.required_abstention_compliance,
            "case_results": [result.to_dict() for result in self.case_results],
            "limitations": list(self.limitations),
            "passed": self.passed,
        }


def run_scientific_constraint_benchmark(
    *,
    include_dynamic: bool = True,
) -> ScientificConstraintBenchmarkReport:
    case_results: list[ConstraintValidationReport] = []
    if include_dynamic:
        for name, builder in DYNAMIC_BUILDERS.items():
            try:
                context = builder()
            except FileNotFoundError:
                if name == "real_bounded_pubmed":
                    continue
                raise
            case_results.append(validate_scientific_constraints(context))

    passed_count = sum(1 for result in case_results if result.passed)
    failed_count = len(case_results) - passed_count

    def _mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 1.0

    abstention_values = [
        value
        for result in case_results
        if (value := result.required_abstention_compliance) is not None
    ]

    return ScientificConstraintBenchmarkReport(
        benchmark_id="scientific_constraint_v1",
        description=(
            "Cross-module scientific constraint consistency benchmark over taxonomy, "
            "linking, own-data, literature, and writer outputs."
        ),
        disclaimer=(
            "This is a deterministic cross-module regression benchmark and does not "
            "constitute human scientific validation."
        ),
        case_count=len(case_results),
        passed_count=passed_count,
        failed_count=failed_count,
        constraint_consistency_rate=_mean([result.constraint_consistency_rate for result in case_results]),
        taxonomy_boundary_violation_rate=_mean(
            [result.taxonomy_boundary_violation_rate for result in case_results]
        ),
        chemical_identity_violation_rate=_mean(
            [result.chemical_identity_violation_rate for result in case_results]
        ),
        causality_violation_rate=_mean([result.causality_violation_rate for result in case_results]),
        retrieval_semantic_violation_rate=_mean(
            [result.retrieval_semantic_violation_rate for result in case_results]
        ),
        provenance_violation_rate=_mean([result.provenance_violation_rate for result in case_results]),
        required_abstention_compliance=_mean(abstention_values) if abstention_values else 1.0,
        case_results=case_results,
        limitations=[
            "Deterministic constraint consistency checks only.",
            "Heuristic text checks reuse writer claim_safety patterns; not semantic completeness.",
            "Passing this benchmark does not constitute human empirical validation.",
        ],
    )


def write_scientific_constraint_reports(
    report: ScientificConstraintBenchmarkReport,
    directory: str | Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "scientific_constraint_benchmark.json"
    md_path = directory / "scientific_constraint_benchmark.md"
    payload = report.to_dict()
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    categories = Counter(result.case_id for result in report.case_results)
    md_lines = [
        "# Scientific Constraint Benchmark Report",
        "",
        report.disclaimer,
        "",
        f"- Case count: **{report.case_count}**",
        f"- Passed: **{report.passed_count}**",
        f"- Failed: **{report.failed_count}**",
        "",
        "## Metrics",
        "",
        f"- constraint_consistency_rate: **{report.constraint_consistency_rate:.4f}**",
        f"- taxonomy_boundary_violation_rate: **{report.taxonomy_boundary_violation_rate:.4f}**",
        f"- chemical_identity_violation_rate: **{report.chemical_identity_violation_rate:.4f}**",
        f"- causality_violation_rate: **{report.causality_violation_rate:.4f}**",
        f"- retrieval_semantic_violation_rate: **{report.retrieval_semantic_violation_rate:.4f}**",
        f"- provenance_violation_rate: **{report.provenance_violation_rate:.4f}**",
        f"- required_abstention_compliance: **{report.required_abstention_compliance:.4f}**",
        "",
        "## Cases",
        "",
    ]
    for case_id, _count in sorted(categories.items()):
        md_lines.append(f"- `{case_id}`")
    md_lines.extend(["", "## Limitations", ""])
    md_lines.extend(f"- {item}" for item in report.limitations)
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return json_path, md_path
