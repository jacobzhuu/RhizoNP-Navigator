from __future__ import annotations

import json
from dataclasses import dataclass
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


@dataclass(frozen=True)
class NaturalProductSourceResolution:
    requested_source: str
    resolved_source: str
    fallback_reason: str | None = None
    snapshot_id: str | None = None
    record_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "requested_source": self.requested_source,
            "resolved_source": self.resolved_source,
        }
        if self.fallback_reason is not None:
            payload["fallback_reason"] = self.fallback_reason
        if self.snapshot_id is not None:
            payload["snapshot_id"] = self.snapshot_id
        if self.record_count is not None:
            payload["record_count"] = self.record_count
        return payload

    def resolved_enum(self) -> NaturalProductSource:
        return NaturalProductSource(self.resolved_source)


def _load_npatlas_snapshot_metadata(snapshot_path: Path) -> dict[str, Any]:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    return dict(payload.get("metadata") or {})


def resolve_natural_product_source(
    source: NaturalProductSource | str,
    *,
    snapshot_path: str | Path = DEFAULT_NPATLAS_SNAPSHOT_PATH,
) -> NaturalProductSource:
    return resolve_natural_product_source_details(
        source,
        snapshot_path=snapshot_path,
    ).resolved_enum()


def resolve_natural_product_source_details(
    source: NaturalProductSource | str,
    *,
    snapshot_path: str | Path = DEFAULT_NPATLAS_SNAPSHOT_PATH,
) -> NaturalProductSourceResolution:
    resolved = source if isinstance(source, NaturalProductSource) else NaturalProductSource(source)
    requested = resolved.value
    if resolved is not NaturalProductSource.AUTO:
        return NaturalProductSourceResolution(
            requested_source=requested,
            resolved_source=requested,
        )

    snap_path = Path(snapshot_path)
    if snap_path.is_file():
        metadata = _load_npatlas_snapshot_metadata(snap_path)
        return NaturalProductSourceResolution(
            requested_source=NaturalProductSource.AUTO.value,
            resolved_source=NaturalProductSource.NPATLAS_BOUNDED.value,
            snapshot_id=str(metadata.get("snapshot_id") or snap_path.parent.name),
            record_count=int(metadata.get("record_count") or 0) or None,
        )

    return NaturalProductSourceResolution(
        requested_source=NaturalProductSource.AUTO.value,
        resolved_source=NaturalProductSource.FIXTURE.value,
        fallback_reason="NPAtlas bounded snapshot unavailable",
    )


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
