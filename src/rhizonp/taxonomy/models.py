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
