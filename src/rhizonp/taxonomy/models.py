from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaxonomyDistance(str, Enum):
    SAME_STRAIN = "SAME_STRAIN"
    SAME_SPECIES = "SAME_SPECIES"
    SAME_GENUS = "SAME_GENUS"
    HIGHER_TAXON = "HIGHER_TAXON"
    UNKNOWN = "UNKNOWN"


class EvidenceTier(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


@dataclass(frozen=True)
class TaxonomyResolutionMetadata:
    requested_source: str
    resolved_source: str
    fallback_reason: str | None = None
    cache_id: str | None = None
    snapshot_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "requested_source": self.requested_source,
            "resolved_source": self.resolved_source,
        }
        if self.fallback_reason is not None:
            payload["fallback_reason"] = self.fallback_reason
        if self.cache_id is not None:
            payload["cache_id"] = self.cache_id
        if self.snapshot_id is not None:
            payload["snapshot_id"] = self.snapshot_id
        return payload


@dataclass(frozen=True)
class NormalizedTaxon:
    canonical_name: str
    rank: str | None = None
    strain: str | None = None
    species: str | None = None
    genus: str | None = None
    family: str | None = None
    external_ids: dict[str, Any] = field(default_factory=dict)
    normalization_status: str = "unresolved"
    confidence: float = 0.0
    resolution: TaxonomyResolutionMetadata | None = None

    @classmethod
    def from_domain_taxon(cls, taxon: Any) -> NormalizedTaxon:
        return cls(
            canonical_name=taxon.canonical_name,
            rank=taxon.rank,
            strain=taxon.strain,
            species=taxon.species,
            genus=taxon.genus,
            family=taxon.family,
            external_ids=dict(taxon.external_ids or {}),
            normalization_status=taxon.normalization_status,
            confidence=1.0 if taxon.normalization_status.startswith("resolved") else 0.5,
        )
