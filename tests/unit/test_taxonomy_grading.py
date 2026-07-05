from __future__ import annotations

from rhizonp.taxonomy.distance import compute_taxonomy_distance, distance_to_evidence_tier
from rhizonp.taxonomy.grading import grade_evidence
from rhizonp.taxonomy.models import EvidenceTier, TaxonomyDistance
from rhizonp.taxonomy.normalization import normalize_taxon_label
from rhizonp.taxonomy.policy import (
    check_overclaim_prevention,
    is_genus_level_observation,
    max_supported_claim,
    tier_allows_strain_claim,
)


def test_normalize_streptomyces_genus_label() -> None:
    taxon = normalize_taxon_label("Streptomyces")
    assert taxon.canonical_name == "Streptomyces"
    assert taxon.rank == "genus"
    assert taxon.genus == "Streptomyces"
    assert taxon.normalization_status == "resolved_exact"


def test_normalize_strain_label() -> None:
    taxon = normalize_taxon_label("Streptomyces hygroscopicus OS-2")
    assert taxon.rank == "strain"
    assert taxon.strain == "OS-2"
    assert taxon.species == "Streptomyces hygroscopicus"


def test_unresolved_label_falls_back_conservatively() -> None:
    taxon = normalize_taxon_label("UnknownActinobacterium XYZ")
    assert taxon.normalization_status == "unresolved"
    assert taxon.confidence <= 0.3


def test_same_strain_distance() -> None:
    query = normalize_taxon_label("Streptomyces hygroscopicus OS-2")
    literature = normalize_taxon_label("Streptomyces hygroscopicus OS-2")
    distance = compute_taxonomy_distance(query, literature)
    assert distance == TaxonomyDistance.SAME_STRAIN
    assert distance_to_evidence_tier(distance) == "A"


def test_same_species_distance() -> None:
    query = normalize_taxon_label("Streptomyces hygroscopicus")
    literature = normalize_taxon_label("Streptomyces hygroscopicus OS-2")
    distance = compute_taxonomy_distance(query, literature)
    assert distance == TaxonomyDistance.SAME_SPECIES
    assert distance_to_evidence_tier(distance) == "B"


def test_same_genus_distance() -> None:
    query = normalize_taxon_label("Streptomyces")
    literature = normalize_taxon_label("Streptomyces hygroscopicus OS-2")
    distance = compute_taxonomy_distance(query, literature)
    assert distance == TaxonomyDistance.SAME_GENUS
    assert distance_to_evidence_tier(distance) == "C"


def test_genus_16s_cannot_support_strain_claim() -> None:
    result = grade_evidence(
        "Streptomyces",
        "Streptomyces hygroscopicus OS-2",
        observation_method="synthetic_16S_fixture",
    )
    assert result.evidence_tier == EvidenceTier.C
    assert result.max_supported_claim == "genus_level_candidate"
    assert not tier_allows_strain_claim(result.evidence_tier)
    assert any("16S" in warning or "strain-level" in warning for warning in result.warnings)


def test_overclaim_prevention_warnings_for_genus_observation() -> None:
    query = normalize_taxon_label("Streptomyces")
    literature = normalize_taxon_label("Streptomyces hygroscopicus OS-2")
    distance = compute_taxonomy_distance(query, literature)
    warnings = check_overclaim_prevention(
        query,
        literature,
        distance,
        observation_method="16S_amplicon",
    )
    assert warnings
    assert is_genus_level_observation(query)


def test_grade_evidence_returns_structured_payload() -> None:
    result = grade_evidence("Streptomyces", "Streptomyces hygroscopicus")
    payload = result.to_dict()
    assert payload["taxonomy_distance"] == TaxonomyDistance.SAME_GENUS.value
    assert payload["evidence_tier"] == "C"
    assert payload["limitations"]
    assert max_supported_claim(result.evidence_tier) == "genus_level_candidate"
