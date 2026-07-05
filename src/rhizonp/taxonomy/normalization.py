from __future__ import annotations

from pathlib import Path
from typing import Any

from rhizonp.taxonomy.fixture_resolver import DEFAULT_TAXONOMY_MAPPING_PATH
from rhizonp.taxonomy.models import NormalizedTaxon
from rhizonp.taxonomy.resolvers import TaxonomyResolverMode


def normalize_taxon_label(
    label: str,
    *,
    mapping_path: str | Path = DEFAULT_TAXONOMY_MAPPING_PATH,
    observation_rank: str | None = None,
    resolver_mode: TaxonomyResolverMode | str | None = None,
    cache_path: str | Path | None = None,
) -> NormalizedTaxon:
    """Normalize a raw taxon label using fixture, bounded NCBI cache, or live NCBI."""
    from rhizonp.taxonomy.resolvers import resolve_taxon_label

    kwargs: dict[str, Any] = {
        "mode": resolver_mode,
        "observation_rank": observation_rank,
        "mapping_path": mapping_path,
    }
    if cache_path is not None:
        kwargs["cache_path"] = cache_path
    return resolve_taxon_label(label, **kwargs)


def normalize_taxon(
    taxon: Any,
    *,
    mapping_path: str | Path = DEFAULT_TAXONOMY_MAPPING_PATH,
    resolver_mode: TaxonomyResolverMode | str | None = None,
    cache_path: str | Path | None = None,
) -> NormalizedTaxon:
    kwargs: dict[str, Any] = {"mapping_path": mapping_path, "resolver_mode": resolver_mode}
    if cache_path is not None:
        kwargs["cache_path"] = cache_path
    if hasattr(taxon, "canonical_name"):
        mapped = normalize_taxon_label(taxon.canonical_name, **kwargs)
        if mapped.normalization_status != "unresolved":
            return mapped
        return NormalizedTaxon.from_domain_taxon(taxon)
    if isinstance(taxon, str):
        return normalize_taxon_label(taxon, **kwargs)
    raise TypeError(f"Unsupported taxon type: {type(taxon)!r}")
