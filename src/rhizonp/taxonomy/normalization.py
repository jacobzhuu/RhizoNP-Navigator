from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from rhizonp.config import PROJECT_ROOT
from rhizonp.taxonomy.models import NormalizedTaxon

DEFAULT_TAXONOMY_MAPPING_PATH = PROJECT_ROOT / "data" / "fixtures" / "taxonomy_mapping.json"


def _normalize_key(label: str) -> str:
    cleaned = re.sub(r"\s+", " ", label.strip().lower())
    cleaned = cleaned.replace("spp.", "sp.")
    return cleaned


@lru_cache
def _load_alias_mapping(path: str) -> dict[str, dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    aliases = payload.get("aliases", {})
    return {_normalize_key(key): value for key, value in aliases.items()}


def normalize_taxon_label(
    label: str,
    *,
    mapping_path: str | Path = DEFAULT_TAXONOMY_MAPPING_PATH,
    observation_rank: str | None = None,
) -> NormalizedTaxon:
    """Normalize a raw taxon label using the local deterministic mapping fixture."""
    key = _normalize_key(label)
    mapping = _load_alias_mapping(str(mapping_path))
    record = mapping.get(key)

    if record is None:
        genus_guess = label.strip().split()[0] if label.strip() else None
        return NormalizedTaxon(
            canonical_name=label.strip(),
            rank=observation_rank,
            genus=genus_guess,
            normalization_status="unresolved",
            confidence=0.2,
        )

    return NormalizedTaxon(
        canonical_name=record["canonical_name"],
        rank=record.get("rank") or observation_rank,
        strain=record.get("strain"),
        species=record.get("species"),
        genus=record.get("genus"),
        family=record.get("family"),
        external_ids=dict(record.get("external_ids", {})),
        normalization_status=record.get("normalization_status", "resolved_exact"),
        confidence=float(record.get("confidence", 1.0)),
    )


def normalize_taxon(
    taxon: Any,
    *,
    mapping_path: str | Path = DEFAULT_TAXONOMY_MAPPING_PATH,
) -> NormalizedTaxon:
    if hasattr(taxon, "canonical_name"):
        mapped = normalize_taxon_label(taxon.canonical_name, mapping_path=mapping_path)
        if mapped.normalization_status != "unresolved":
            return mapped
        return NormalizedTaxon.from_domain_taxon(taxon)
    if isinstance(taxon, str):
        return normalize_taxon_label(taxon, mapping_path=mapping_path)
    raise TypeError(f"Unsupported taxon type: {type(taxon)!r}")
