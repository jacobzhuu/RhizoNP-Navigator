from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rhizonp.writer.models import Claim, EvidenceInput


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


@dataclass(frozen=True)
class HeuristicFaithfulnessDiagnostic:
    overlap_ratio: float
    diagnostic_label: str
    human_faithfulness_pending: bool = True
    notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "overlap_ratio": self.overlap_ratio,
            "diagnostic_label": self.diagnostic_label,
            "human_faithfulness_pending": self.human_faithfulness_pending,
            "evaluation_kind": "heuristic_faithfulness_diagnostic",
        }
        if self.notes:
            payload["notes"] = list(self.notes)
        return payload


def heuristic_faithfulness_diagnostic(
    *,
    supporting_span: str | None,
    claim_text: str,
) -> HeuristicFaithfulnessDiagnostic:
    if not supporting_span:
        return HeuristicFaithfulnessDiagnostic(
            overlap_ratio=0.0,
            diagnostic_label="missing_supporting_span",
            notes=["No supporting span available for heuristic check."],
        )
    claim_tokens = _tokenize(claim_text)
    span_tokens = _tokenize(supporting_span)
    if not claim_tokens:
        return HeuristicFaithfulnessDiagnostic(
            overlap_ratio=0.0,
            diagnostic_label="empty_claim_tokens",
        )
    overlap = claim_tokens & span_tokens
    ratio = len(overlap) / len(claim_tokens)
    if ratio >= 0.25:
        label = "weak_lexical_overlap"
    elif ratio > 0.0:
        label = "minimal_lexical_overlap"
    else:
        label = "no_lexical_overlap"
    return HeuristicFaithfulnessDiagnostic(
        overlap_ratio=round(ratio, 4),
        diagnostic_label=label,
        notes=[
            "Heuristic overlap only; not human-validated faithfulness.",
            "Retrieval relevance does not imply scientific correctness.",
        ],
    )


def evaluate_claim_faithfulness_diagnostics(
    claims: list[Claim],
    evidence_by_id: dict[Any, EvidenceInput],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for claim in claims:
        if not claim.evidence_refs:
            continue
        ref = claim.evidence_refs[0]
        item = evidence_by_id.get(ref)
        if item is None:
            continue
        diagnostic = heuristic_faithfulness_diagnostic(
            supporting_span=item.supporting_span,
            claim_text=claim.text,
        )
        diagnostics.append(
            {
                "claim_text": claim.text,
                "evidence_id": str(ref),
                **diagnostic.to_dict(),
            }
        )
    return diagnostics
