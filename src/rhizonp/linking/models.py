from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BioactivityRecord:
    activity_type: str
    target: str | None = None
    evidence_level: str = "reported"
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NaturalProductFixtureRecord:
    key: str
    compound_name: str
    producer_taxon: str
    source_database: str
    external_record_id: str
    bioactivity: BioactivityRecord | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "key": self.key,
            "compound_name": self.compound_name,
            "producer_taxon": self.producer_taxon,
            "source_database": self.source_database,
            "external_record_id": self.external_record_id,
            "provenance": dict(self.provenance),
        }
        if self.bioactivity is not None:
            payload["bioactivity"] = {
                "activity_type": self.bioactivity.activity_type,
                "target": self.bioactivity.target,
                "evidence_level": self.bioactivity.evidence_level,
                "provenance": dict(self.bioactivity.provenance),
            }
        return payload
