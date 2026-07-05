from __future__ import annotations

import json
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from rhizonp.config import PROJECT_ROOT
from rhizonp.ingestion.npatlas import (
    DEFAULT_NPATLAS_SNAPSHOT_PATH,
    NormalizedNPAtlasRecord,
    load_bounded_npatlas_snapshot,
)
from rhizonp.linking.compound_normalization import normalize_compound_name
from rhizonp.linking.models import BioactivityRecord, NaturalProductFixtureRecord

DEFAULT_NP_FIXTURE_PATH = PROJECT_ROOT / "data" / "fixtures" / "natural_products_demo.json"


class NaturalProductSource(str, Enum):
    FIXTURE = "fixture"
    NPATLAS_BOUNDED = "npatlas_bounded"
    AUTO = "auto"


def resolve_natural_product_source(
    source: NaturalProductSource | str,
    *,
    snapshot_path: str | Path = DEFAULT_NPATLAS_SNAPSHOT_PATH,
) -> NaturalProductSource:
    resolved = source if isinstance(source, NaturalProductSource) else NaturalProductSource(source)
    if resolved is not NaturalProductSource.AUTO:
        return resolved
    if Path(snapshot_path).is_file():
        return NaturalProductSource.NPATLAS_BOUNDED
    return NaturalProductSource.FIXTURE


def _normalized_to_fixture_record(record: NormalizedNPAtlasRecord) -> NaturalProductFixtureRecord:
    return NaturalProductFixtureRecord(
        key=f"npatlas_{record.npaid.lower()}",
        compound_name=record.compound_name,
        producer_taxon=record.producer_taxon,
        source_database=record.source_database,
        external_record_id=record.external_record_id,
        bioactivity=None,
        provenance=dict(record.provenance),
    )


@lru_cache
def load_natural_product_fixture(
    fixture_path: str | Path = DEFAULT_NP_FIXTURE_PATH,
) -> list[NaturalProductFixtureRecord]:
    payload = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    records: list[NaturalProductFixtureRecord] = []
    for record in payload.get("records", []):
        bio_payload = record.get("bioactivity")
        bioactivity = None
        if isinstance(bio_payload, dict):
            bioactivity = BioactivityRecord(
                activity_type=bio_payload["activity_type"],
                target=bio_payload.get("target"),
                evidence_level=bio_payload.get("evidence_level", "reported"),
                provenance=dict(bio_payload.get("provenance", {})),
            )
        records.append(
            NaturalProductFixtureRecord(
                key=record["key"],
                compound_name=normalize_compound_name(record["compound_name"], fixture_path=fixture_path),
                producer_taxon=record["producer_taxon"],
                source_database=record["source_database"],
                external_record_id=record["external_record_id"],
                bioactivity=bioactivity,
                provenance=dict(record.get("provenance", {})),
            )
        )
    return records


@lru_cache
def load_bounded_npatlas_records(
    snapshot_path: str | Path = DEFAULT_NPATLAS_SNAPSHOT_PATH,
) -> list[NaturalProductFixtureRecord]:
    normalized = load_bounded_npatlas_snapshot(snapshot_path)
    return [_normalized_to_fixture_record(record) for record in normalized]


def load_natural_product_records(
    *,
    source: NaturalProductSource | str = NaturalProductSource.FIXTURE,
    fixture_path: str | Path = DEFAULT_NP_FIXTURE_PATH,
    snapshot_path: str | Path = DEFAULT_NPATLAS_SNAPSHOT_PATH,
) -> list[NaturalProductFixtureRecord]:
    resolved = resolve_natural_product_source(source, snapshot_path=snapshot_path)
    if resolved is NaturalProductSource.NPATLAS_BOUNDED:
        return load_bounded_npatlas_records(snapshot_path)
    return load_natural_product_fixture(fixture_path)


def fixture_record_to_dict(record: NaturalProductFixtureRecord) -> dict[str, Any]:
    return record.to_dict()
