from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from rhizonp.writer.models import GroundedAnswer


@dataclass(frozen=True)
class ForbiddenClaimReport:
    violations: list[str] = field(default_factory=list)
    checked_patterns: list[str] = field(default_factory=list)
    diagnostic_kind: str = "heuristic_forbidden_claim_check"

    @property
    def violation_count(self) -> int:
        return len(self.violations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "violation_count": self.violation_count,
            "violations": list(self.violations),
            "checked_patterns": list(self.checked_patterns),
            "diagnostic_kind": self.diagnostic_kind,
            "notes": [
                "Case-specific pattern matching only; not a complete semantic safety guarantee.",
            ],
        }


def _collect_text(answer: GroundedAnswer) -> list[tuple[str, str]]:
    segments: list[tuple[str, str]] = [("answer", answer.answer)]
    for index, claim in enumerate(answer.claims, start=1):
        segments.append((f"claim_{index}", claim.text))
    return segments


def check_forbidden_claim_patterns(
    answer: GroundedAnswer,
    patterns: list[str],
) -> ForbiddenClaimReport:
    violations: list[str] = []
    normalized_patterns = [pattern for pattern in patterns if pattern.strip()]
    for label, text in _collect_text(answer):
        lowered = text.lower()
        for pattern in normalized_patterns:
            if pattern.lower() in lowered:
                violations.append(f"{label}: matched forbidden pattern `{pattern}`")
                continue
            try:
                if re.search(pattern, text, flags=re.IGNORECASE):
                    violations.append(f"{label}: matched forbidden regex `{pattern}`")
            except re.error:
                continue
    return ForbiddenClaimReport(
        violations=list(dict.fromkeys(violations)),
        checked_patterns=normalized_patterns,
    )


GLOBAL_OVERCLAIM_PATTERNS: dict[str, list[str]] = {
    "taxonomy_overclaim": [
        "detected strain",
        "this sample produces",
        "strain produces",
        "strain-level production is confirmed",
    ],
    "chemical_identity_overclaim": [
        r"Feature_M123 is ",
        "structure-confirmed",
        "confirmed compound identity",
    ],
    "causality_overclaim": [
        " causes ",
        "causal link",
        "demonstrates causation",
        "proves causation",
    ],
    "production_overclaim_from_mention": [
        "confirmed production",
        "production is confirmed",
        "produces rapamycin in this sample",
    ],
}


def classify_overclaim_violations(answer: GroundedAnswer) -> dict[str, ForbiddenClaimReport]:
    return {
        category: check_forbidden_claim_patterns(answer, patterns)
        for category, patterns in GLOBAL_OVERCLAIM_PATTERNS.items()
    }
