from __future__ import annotations

from dataclasses import replace
from enum import Enum
from pathlib import Path
from typing import Any

from rhizonp.config import get_settings
from rhizonp.taxonomy.fixture_resolver import normalize_taxon_label_from_fixture
from rhizonp.taxonomy.models import NormalizedTaxon, TaxonomyResolutionMetadata
from rhizonp.taxonomy.ncbi_resolver import (
    DEFAULT_NCBI_TAXONOMY_CACHE_PATH,
    NCBITaxonomyClient,
    get_ncbi_cache_metadata,
    lookup_cached_ncbi_taxonomy,
    ncbi_record_to_normalized_taxon,
)


class TaxonomyResolverMode(str, Enum):
    FIXTURE = "fixture"
    LOCAL_FIXTURE = "local_fixture"
    NCBI_CACHED = "ncbi_cached"
    NCBI_BOUNDED = "ncbi_bounded"
    NCBI_LIVE = "ncbi_live"
    AUTO = "auto"
    UNKNOWN = "unknown"


_NCBI_BOUNDED_MODES = frozenset(
    {
        TaxonomyResolverMode.NCBI_CACHED,
        TaxonomyResolverMode.NCBI_BOUNDED,
        "ncbi_cached",
        "ncbi_bounded",
    }
)
_LOCAL_FIXTURE_MODES = frozenset(
    {
        TaxonomyResolverMode.FIXTURE,
        TaxonomyResolverMode.LOCAL_FIXTURE,
        "fixture",
        "local_fixture",
    }
)


def _coerce_resolver_mode(mode: TaxonomyResolverMode | str) -> TaxonomyResolverMode:
    if isinstance(mode, TaxonomyResolverMode):
        return mode
    aliases = {
        "local_fixture": TaxonomyResolverMode.FIXTURE,
        "ncbi_bounded": TaxonomyResolverMode.NCBI_BOUNDED,
    }
    return aliases.get(mode, TaxonomyResolverMode(mode))


def _attach_resolution(
    taxon: NormalizedTaxon,
    *,
    requested_source: str,
    resolved_source: str,
    fallback_reason: str | None = None,
    cache_id: str | None = None,
) -> NormalizedTaxon:
    metadata = TaxonomyResolutionMetadata(
        requested_source=requested_source,
        resolved_source=resolved_source,
        fallback_reason=fallback_reason,
        cache_id=cache_id,
    )
    return replace(taxon, resolution=metadata)


def _unresolved_taxon(
    label: str,
    *,
    observation_rank: str | None = None,
    requested_source: str,
    resolved_source: str = "unknown",
    fallback_reason: str | None = None,
    cache_id: str | None = None,
) -> NormalizedTaxon:
    genus_guess = label.strip().split()[0] if label.strip() else None
    return _attach_resolution(
        NormalizedTaxon(
            canonical_name=label.strip(),
            rank=observation_rank,
            genus=genus_guess,
            normalization_status="unresolved",
            confidence=0.2,
        ),
        requested_source=requested_source,
        resolved_source=resolved_source,
        fallback_reason=fallback_reason,
        cache_id=cache_id,
    )


def _cache_metadata_or_none(cache_path: str | Path) -> dict[str, Any] | None:
    path = Path(cache_path)
    if not path.is_file():
        return None
    try:
        return get_ncbi_cache_metadata(cache_path)
    except (OSError, ValueError):
        return None


def _resolve_auto(
    label: str,
    *,
    observation_rank: str | None,
    fixture_kwargs: dict[str, Any],
    cache_path: str | Path,
) -> NormalizedTaxon:
    requested = TaxonomyResolverMode.AUTO.value
    cache_meta = _cache_metadata_or_none(cache_path)
    cache_id = cache_meta.get("cache_id") if cache_meta else None

    if cache_meta is not None:
        cached = lookup_cached_ncbi_taxonomy(label, cache_path=cache_path)
        if cached is not None:
            return _attach_resolution(
                cached,
                requested_source=requested,
                resolved_source=TaxonomyResolverMode.NCBI_BOUNDED.value,
                cache_id=cache_id,
            )

    fixture_result = normalize_taxon_label_from_fixture(label, **fixture_kwargs)
    if fixture_result.normalization_status != "unresolved":
        fallback_reason = (
            "ncbi_cache_miss"
            if cache_meta is not None
            else "ncbi_bounded_cache_unavailable"
        )
        return _attach_resolution(
            fixture_result,
            requested_source=requested,
            resolved_source=TaxonomyResolverMode.FIXTURE.value,
            fallback_reason=fallback_reason,
            cache_id=cache_id,
        )

    fallback_reason = (
        "ncbi_cache_miss_and_fixture_unresolved"
        if cache_meta is not None
        else "ncbi_bounded_cache_unavailable"
    )
    return _attach_resolution(
        fixture_result,
        requested_source=requested,
        resolved_source=TaxonomyResolverMode.UNKNOWN.value,
        fallback_reason=fallback_reason,
        cache_id=cache_id,
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
    resolved_mode = _coerce_resolver_mode(mode)

    fixture_kwargs: dict[str, Any] = {}
    if mapping_path is not None:
        fixture_kwargs["mapping_path"] = mapping_path
    if observation_rank is not None:
        fixture_kwargs["observation_rank"] = observation_rank

    cache_meta = _cache_metadata_or_none(cache_path)
    cache_id = cache_meta.get("cache_id") if cache_meta else None

    if resolved_mode in _LOCAL_FIXTURE_MODES:
        fixture_result = normalize_taxon_label_from_fixture(label, **fixture_kwargs)
        return _attach_resolution(
            fixture_result,
            requested_source=TaxonomyResolverMode.FIXTURE.value,
            resolved_source=TaxonomyResolverMode.FIXTURE.value,
            cache_id=cache_id,
        )

    if resolved_mode in _NCBI_BOUNDED_MODES:
        cached = lookup_cached_ncbi_taxonomy(label, cache_path=cache_path)
        if cached is not None:
            return _attach_resolution(
                cached,
                requested_source=TaxonomyResolverMode.NCBI_BOUNDED.value,
                resolved_source=TaxonomyResolverMode.NCBI_BOUNDED.value,
                cache_id=cache_id,
            )
        return _unresolved_taxon(
            label,
            observation_rank=observation_rank,
            requested_source=TaxonomyResolverMode.NCBI_BOUNDED.value,
            resolved_source=TaxonomyResolverMode.UNKNOWN.value,
            fallback_reason="ncbi_cache_miss",
            cache_id=cache_id,
        )

    if resolved_mode is TaxonomyResolverMode.NCBI_LIVE:
        client = live_client or NCBITaxonomyClient()
        taxid = client.search_taxid(label)
        if not taxid:
            return _unresolved_taxon(
                label,
                observation_rank=observation_rank,
                requested_source=TaxonomyResolverMode.NCBI_LIVE.value,
                fallback_reason="ncbi_live_search_miss",
            )
        records = client.fetch_records([taxid])
        if not records:
            return _unresolved_taxon(
                label,
                observation_rank=observation_rank,
                requested_source=TaxonomyResolverMode.NCBI_LIVE.value,
                fallback_reason="ncbi_live_fetch_miss",
            )
        record = replace(records[0], query_label=label)
        return _attach_resolution(
            ncbi_record_to_normalized_taxon(record),
            requested_source=TaxonomyResolverMode.NCBI_LIVE.value,
            resolved_source=TaxonomyResolverMode.NCBI_BOUNDED.value,
        )

    if resolved_mode is TaxonomyResolverMode.AUTO:
        return _resolve_auto(
            label,
            observation_rank=observation_rank,
            fixture_kwargs=fixture_kwargs,
            cache_path=cache_path,
        )

    return _unresolved_taxon(
        label,
        observation_rank=observation_rank,
        requested_source=str(resolved_mode.value),
        fallback_reason="unsupported_resolver_mode",
    )
