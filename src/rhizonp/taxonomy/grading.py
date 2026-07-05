from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rhizonp.taxonomy.distance import compute_taxonomy_distance, distance_to_evidence_tier
from rhizonp.taxonomy.models import EvidenceTier, NormalizedTaxon, TaxonomyDistance
from rhizonp.taxonomy.normalization import normalize_taxon
from rhizonp.taxonomy.policy import check_overclaim_prevention, max_supported_claim


@dataclass(frozen=True)
class EvidenceGradingResult:
    query_taxon: NormalizedTaxon
    literature_taxon: NormalizedTaxon
    taxonomy_distance: TaxonomyDistance
    evidence_tier: EvidenceTier
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    max_supported_claim: str = "retrieval_clue_only"
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_taxon": {
                "canonical_name": self.query_taxon.canonical_name,
                "rank": self.query_taxon.rank,
                "strain": self.query_taxon.strain,
                "species": self.query_taxon.species,
                "genus": self.query_taxon.genus,
                "normalization_status": self.query_taxon.normalization_status,
                "confidence": self.query_taxon.confidence,
            },
            "literature_taxon": {
                "canonical_name": self.literature_taxon.canonical_name,
                "rank": self.literature_taxon.rank,
                "strain": self.literature_taxon.strain,
                "species": self.literature_taxon.species,
                "genus": self.literature_taxon.genus,
                "normalization_status": self.literature_taxon.normalization_status,
                "confidence": self.literature_taxon.confidence,
            },
            "taxonomy_distance": self.taxonomy_distance.value,
            "evidence_tier": self.evidence_tier.value,
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "max_supported_claim": self.max_supported_claim,
            "provenance": dict(self.provenance),
        }


def grade_evidence(
    query_label: str | Any,
    literature_label: str | Any,
    *,
    observation_method: str | None = None,
    mapping_path: str | None = None,
) -> EvidenceGradingResult:
    kwargs: dict[str, Any] = {}
    if mapping_path is not None:
        kwargs["mapping_path"] = mapping_path

    query_taxon = normalize_taxon(query_label, **kwargs)
    literature_taxon = normalize_taxon(literature_label, **kwargs)
    distance = compute_taxonomy_distance(query_taxon, literature_taxon)
    tier_value = distance_to_evidence_tier(distance)
    tier = EvidenceTier(tier_value)

    warnings = check_overclaim_prevention(
        query_taxon,
        literature_taxon,
        distance,
        observation_method=observation_method,
    )
    limitations = list(warnings)
    if query_taxon.normalization_status == "unresolved":
        limitations.append("Query taxon normalization unresolved; using conservative fallback.")
    if literature_taxon.normalization_status == "unresolved":
        limitations.append("Literature taxon normalization unresolved; using conservative fallback.")

    return EvidenceGradingResult(
        query_taxon=query_taxon,
        literature_taxon=literature_taxon,
        taxonomy_distance=distance,
        evidence_tier=tier,
        warnings=warnings,
        limitations=limitations,
        max_supported_claim=max_supported_claim(tier),
        provenance={
            "grading_engine": "rhizonp.taxonomy.grading",
            "observation_method": observation_method,
            "fixture_mapping": True,
        },
    )
