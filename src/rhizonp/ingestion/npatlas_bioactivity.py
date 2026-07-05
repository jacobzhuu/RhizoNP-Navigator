from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

NPATLAS_LICENSE = "CC-BY-NC-4.0"

_ORIGIN_REFERENCE_EVIDENCE_LEVEL = "origin_reference_reported"
_DESCRIPTIVE_EVIDENCE_LEVEL = "origin_reference_descriptive"

_ACTIVITY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bantifungal\b", flags=re.IGNORECASE), "antifungal"),
    (re.compile(r"\bantibacterial\b", flags=re.IGNORECASE), "antibacterial"),
    (re.compile(r"\bantibiotic\b", flags=re.IGNORECASE), "antibacterial"),
    (re.compile(r"\binhibitors?\b", flags=re.IGNORECASE), "inhibitor"),
    (re.compile(r"\bcytotoxic\b", flags=re.IGNORECASE), "cytotoxic"),
    (re.compile(r"\biron chelator\b", flags=re.IGNORECASE), "iron_chelator"),
)

_ACTIVE_AGAINST_PATTERN = re.compile(
    r"\bactive against ([^,\.;]+)",
    flags=re.IGNORECASE,
)


def _bioactivity_provenance(
    *,
    npaid: str,
    origin_reference: Mapping[str, Any],
    source_url: str,
    extraction_method: str,
) -> dict[str, Any]:
    return {
        "source": "npatlas",
        "npaid": npaid,
        "license": NPATLAS_LICENSE,
        "source_url": source_url,
        "real_bounded_npatlas": True,
        "not_synthetic_fixture": True,
        "extraction_method": extraction_method,
        "origin_reference": {
            "doi": origin_reference.get("doi"),
            "pmid": origin_reference.get("pmid"),
            "title": origin_reference.get("title"),
            "journal": origin_reference.get("journal"),
            "year": origin_reference.get("year"),
        },
        "limitations": [
            "Derived from NPAtlas origin-reference title text only.",
            "Not an assay-validated bioactivity record.",
            "NPAtlas compound API does not expose structured bioactivity fields.",
        ],
    }


def derive_bioactivity_summary(origin_reference: Mapping[str, Any]) -> str | None:
    title = str(origin_reference.get("title") or "").strip()
    if not title:
        return None
    return title


def derive_structured_bioactivity(
    *,
    npaid: str,
    origin_reference: Mapping[str, Any],
    source_url: str,
) -> dict[str, Any] | None:
    title = str(origin_reference.get("title") or "").strip()
    if not title:
        return None

    active_match = _ACTIVE_AGAINST_PATTERN.search(title)
    if active_match:
        target = active_match.group(1).strip()
        return {
            "activity_type": "active_against",
            "target": target or None,
            "evidence_level": _ORIGIN_REFERENCE_EVIDENCE_LEVEL,
            "provenance": _bioactivity_provenance(
                npaid=npaid,
                origin_reference=origin_reference,
                source_url=source_url,
                extraction_method="origin_reference_title_active_against",
            ),
        }

    for pattern, activity_type in _ACTIVITY_PATTERNS:
        if pattern.search(title):
            target = None
            if activity_type == "iron_chelator":
                target = "iron"
            return {
                "activity_type": activity_type,
                "target": target,
                "evidence_level": _ORIGIN_REFERENCE_EVIDENCE_LEVEL,
                "provenance": _bioactivity_provenance(
                    npaid=npaid,
                    origin_reference=origin_reference,
                    source_url=source_url,
                    extraction_method="origin_reference_title_keyword",
                ),
            }

    return None


def derive_npatlas_bioactivity_fields(
    *,
    npaid: str,
    origin_reference: Mapping[str, Any],
    source_url: str,
) -> tuple[dict[str, Any] | None, str | None]:
    summary = derive_bioactivity_summary(origin_reference)
    structured = derive_structured_bioactivity(
        npaid=npaid,
        origin_reference=origin_reference,
        source_url=source_url,
    )
    if structured is None and summary:
        structured = {
            "activity_type": "origin_reference_report",
            "target": None,
            "evidence_level": _DESCRIPTIVE_EVIDENCE_LEVEL,
            "provenance": _bioactivity_provenance(
                npaid=npaid,
                origin_reference=origin_reference,
                source_url=source_url,
                extraction_method="origin_reference_title_descriptive",
            ),
        }
    return structured, summary
