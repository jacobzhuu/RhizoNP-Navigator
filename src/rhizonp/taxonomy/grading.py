from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rhizonp.taxonomy.distance import compute_taxonomy_distance, distance_to_evidence_tier
from rhizonp.taxonomy.models import EvidenceTier, NormalizedTaxon, TaxonomyDistance
from rhizonp.taxonomy.normalization import normalize_taxon
from rhizonp.taxonomy.policy import check_overclaim_prevention, max_supported_claim


def _taxon_dict(taxon: NormalizedTaxon) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "canonical_name": taxon.canonical_name,
        "rank": taxon.rank,
        "strain": taxon.strain,
        "species": taxon.species,
        "genus": taxon.genus,
        "normalization_status": taxon.normalization_status,
        "confidence": taxon.confidence,
    }
    if taxon.external_ids:
        payload["external_ids"] = dict(taxon.external_ids)
    if taxon.resolution is not None:
        payload["resolution"] = taxon.resolution.to_dict()
    return payload


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
            "query_taxon": _taxon_dict(self.query_taxon),
            "literature_taxon": _taxon_dict(self.literature_taxon),
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
    resolver_mode: str | None = None,
    taxonomy_source: str | None = None,
) -> EvidenceGradingResult:
    kwargs: dict[str, Any] = {}
    if mapping_path is not None:
        kwargs["mapping_path"] = mapping_path
    resolved_mode = taxonomy_source if taxonomy_source is not None else resolver_mode
    if resolved_mode is not None:
        kwargs["resolver_mode"] = resolved_mode

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

    provenance: dict[str, Any] = {
        "grading_engine": "rhizonp.taxonomy.grading",
        "observation_method": observation_method,
        "taxonomy_source": resolved_mode or "settings_default",
    }
    if query_taxon.resolution is not None:
        provenance["query_resolution"] = query_taxon.resolution.to_dict()
    if literature_taxon.resolution is not None:
        provenance["literature_resolution"] = literature_taxon.resolution.to_dict()

    return EvidenceGradingResult(
        query_taxon=query_taxon,
        literature_taxon=literature_taxon,
        taxonomy_distance=distance,
        evidence_tier=tier,
        warnings=warnings,
        limitations=limitations,
        max_supported_claim=max_supported_claim(tier),
        provenance=provenance,
    )
