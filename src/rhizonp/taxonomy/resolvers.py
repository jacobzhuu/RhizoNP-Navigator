from __future__ import annotations

from dataclasses import replace
from enum import Enum
from pathlib import Path
from typing import Any

from rhizonp.config import get_settings
from rhizonp.taxonomy.fixture_resolver import normalize_taxon_label_from_fixture
from rhizonp.taxonomy.models import NormalizedTaxon
from rhizonp.taxonomy.ncbi_resolver import (
    DEFAULT_NCBI_TAXONOMY_CACHE_PATH,
    NCBITaxonomyClient,
    lookup_cached_ncbi_taxonomy,
    ncbi_record_to_normalized_taxon,
)


class TaxonomyResolverMode(str, Enum):
    FIXTURE = "fixture"
    NCBI_CACHED = "ncbi_cached"
    NCBI_LIVE = "ncbi_live"
    AUTO = "auto"


def _unresolved_taxon(label: str, *, observation_rank: str | None = None) -> NormalizedTaxon:
    genus_guess = label.strip().split()[0] if label.strip() else None
    return NormalizedTaxon(
        canonical_name=label.strip(),
        rank=observation_rank,
        genus=genus_guess,
        normalization_status="unresolved",
        confidence=0.2,
    )


def resolve_taxon_label(
    label: str,
    *,
    mode: TaxonomyResolverMode | str | None = None,
    observation_rank: str | None = None,
    mapping_path: str | Path | None = None,
    cache_path: str | Path = DEFAULT_NCBI_TAXONOMY_CACHE_PATH,
    live_client: NCBITaxonomyClient | None = None,
) -> NormalizedTaxon:
    """Resolve a raw taxon label using fixture, bounded NCBI cache, or live NCBI."""

    if mode is None:
        mode = get_settings().taxonomy_resolver
    resolved_mode = mode if isinstance(mode, TaxonomyResolverMode) else TaxonomyResolverMode(mode)

    fixture_kwargs: dict[str, Any] = {}
    if mapping_path is not None:
        fixture_kwargs["mapping_path"] = mapping_path
    if observation_rank is not None:
        fixture_kwargs["observation_rank"] = observation_rank

    if resolved_mode is TaxonomyResolverMode.FIXTURE:
        return normalize_taxon_label_from_fixture(label, **fixture_kwargs)

    if resolved_mode is TaxonomyResolverMode.NCBI_CACHED:
        cached = lookup_cached_ncbi_taxonomy(label, cache_path=cache_path)
        return cached or _unresolved_taxon(label, observation_rank=observation_rank)

    if resolved_mode is TaxonomyResolverMode.NCBI_LIVE:
        client = live_client or NCBITaxonomyClient()
        taxid = client.search_taxid(label)
        if not taxid:
            return _unresolved_taxon(label, observation_rank=observation_rank)
        records = client.fetch_records([taxid])
        if not records:
            return _unresolved_taxon(label, observation_rank=observation_rank)
        record = replace(records[0], query_label=label)
        return ncbi_record_to_normalized_taxon(record)

    fixture_result = normalize_taxon_label_from_fixture(label, **fixture_kwargs)
    if fixture_result.normalization_status != "unresolved":
        return fixture_result

    cached = lookup_cached_ncbi_taxonomy(label, cache_path=cache_path)
    if cached is not None:
        return cached

    return fixture_result
