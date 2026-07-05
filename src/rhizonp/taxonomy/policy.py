from __future__ import annotations

from rhizonp.taxonomy.models import EvidenceTier, NormalizedTaxon, TaxonomyDistance

GENUS_LEVEL_RANKS = frozenset({"genus", "family", "order", "class", "phylum", "kingdom"})
STRAIN_LEVEL_RANKS = frozenset({"strain", "isolate"})


def is_genus_level_observation(taxon: NormalizedTaxon) -> bool:
    rank = (taxon.rank or "").lower()
    if rank in GENUS_LEVEL_RANKS:
        return True
    if rank in STRAIN_LEVEL_RANKS:
        return False
    return taxon.strain is None and taxon.species is None and taxon.genus is not None


def is_strain_level_evidence(taxon: NormalizedTaxon) -> bool:
    rank = (taxon.rank or "").lower()
    if rank in STRAIN_LEVEL_RANKS:
        return True
    return taxon.strain is not None


def check_overclaim_prevention(
    query_taxon: NormalizedTaxon,
    literature_taxon: NormalizedTaxon,
    distance: TaxonomyDistance,
    *,
    observation_method: str | None = None,
) -> list[str]:
    """Return warnings when taxonomy evidence cannot support a stronger claim."""
    warnings: list[str] = []
    method = (observation_method or "").lower()
    is_16s = "16s" in method or query_taxon.rank == "genus"

    if is_genus_level_observation(query_taxon) and distance in {
        TaxonomyDistance.SAME_GENUS,
        TaxonomyDistance.HIGHER_TAXON,
        TaxonomyDistance.UNKNOWN,
    }:
        warnings.append(
            "Genus-level or unresolved observation cannot support strain-level production claims."
        )

    if is_16s and is_strain_level_evidence(literature_taxon):
        warnings.append(
            "16S genus-level observation must not be promoted to strain-level production "
            "based on literature from a different strain."
        )

    if distance == TaxonomyDistance.SAME_GENUS:
        warnings.append(
            "Same-genus evidence is candidate-level only; it does not prove this sample "
            "produces the compound."
        )

    if distance == TaxonomyDistance.UNKNOWN:
        warnings.append(
            "Taxonomy could not be resolved conservatively; evidence tier downgraded."
        )

    return warnings


def tier_allows_strain_claim(tier: EvidenceTier | str) -> bool:
    value = tier.value if isinstance(tier, EvidenceTier) else str(tier)
    return value in {EvidenceTier.A.value, "A", "Tier A", "same_strain"}


def tier_allows_species_claim(tier: EvidenceTier | str) -> bool:
    value = tier.value if isinstance(tier, EvidenceTier) else str(tier)
    return value in {
        EvidenceTier.A.value,
        EvidenceTier.B.value,
        "A",
        "B",
        "Tier A",
        "Tier B",
        "same_strain",
        "same_species",
    }


def max_supported_claim(tier: EvidenceTier | str) -> str:
    value = tier.value if isinstance(tier, EvidenceTier) else str(tier)
    if value in {EvidenceTier.A.value, "A", "Tier A", "same_strain"}:
        return "strain_level_production"
    if value in {EvidenceTier.B.value, "B", "Tier B", "same_species"}:
        return "species_level_production"
    if value in {EvidenceTier.C.value, "C", "Tier C", "same_genus"}:
        return "genus_level_candidate"
    return "retrieval_clue_only"
