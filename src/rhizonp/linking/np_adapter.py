from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from rhizonp.config import PROJECT_ROOT
from rhizonp.linking.compound_normalization import normalize_compound_name
from rhizonp.linking.models import BioactivityRecord, NaturalProductFixtureRecord

DEFAULT_NP_FIXTURE_PATH = PROJECT_ROOT / "data" / "fixtures" / "natural_products_demo.json"


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


def fixture_record_to_dict(record: NaturalProductFixtureRecord) -> dict[str, Any]:
    return record.to_dict()
