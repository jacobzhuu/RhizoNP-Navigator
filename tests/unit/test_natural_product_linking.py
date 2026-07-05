from __future__ import annotations

from rhizonp.linking.candidate_engine import link_natural_product_candidates
from rhizonp.linking.compound_normalization import normalize_compound_name
from rhizonp.linking.np_adapter import NaturalProductSource, load_natural_product_fixture


def test_compound_alias_normalization() -> None:
    assert normalize_compound_name("sirolimus") == "Rapamycin"
    assert normalize_compound_name("FixturePolyketide-A") == "FixturePolyketide-A"


def test_fixture_adapter_loads_records() -> None:
    records = load_natural_product_fixture()
    assert len(records) >= 3
    assert records[0].source_database == "synthetic_fixture"
    assert all(record.provenance.get("fixture") for record in records)


_FIXTURE = {"record_source": NaturalProductSource.FIXTURE}


def test_link_candidates_ranks_by_taxonomy_and_compound_match() -> None:
    matrix = link_natural_product_candidates(
        "Streptomyces hygroscopicus OS-2",
        metabolite_name="rapamycin",
        **_FIXTURE,
    )
    assert matrix.rows
    top = matrix.rows[0]
    assert top.compound_name == "Rapamycin"
    assert top.compound_match is True
    assert top.evidence_tier == "A"
    assert top.rank == 1


def test_genus_query_gets_conservative_tier_for_strain_record() -> None:
    matrix = link_natural_product_candidates(
        "Streptomyces",
        observation_method="synthetic_16S_fixture",
        **_FIXTURE,
    )
    strain_row = next(row for row in matrix.rows if "OS-2" in row.producer_taxon)
    assert strain_row.evidence_tier == "C"
    assert strain_row.status == "PARTIALLY_SUPPORTED"
    assert any("strain-level" in warning.lower() for warning in strain_row.warnings)


def test_unknown_metabolite_feature_is_not_supported_without_compound_match() -> None:
    matrix = link_natural_product_candidates(
        "Streptomyces",
        metabolite_name="Feature_M123",
        observation_method="synthetic_16S_fixture",
        **_FIXTURE,
    )
    top = matrix.rows[0]
    assert top.compound_match is False
    assert top.status == "PARTIALLY_SUPPORTED"
    assert top.evidence_tier == "C"
    assert top.taxonomy_distance == "SAME_GENUS"
    assert any("did not match any known compound name" in item for item in top.limitations)


def test_genus_vs_genus_producer_with_named_compound_match_can_still_be_supported() -> None:
    matrix = link_natural_product_candidates(
        "Streptomyces",
        metabolite_name="FixturePolyketide-A",
        **_FIXTURE,
    )
    matched = next(row for row in matrix.rows if row.compound_match)
    assert matched.evidence_tier == "C"
    assert matched.status == "PARTIALLY_SUPPORTED"


def test_candidate_matrix_preserves_provenance() -> None:
    matrix = link_natural_product_candidates("Streptomyces", **_FIXTURE)
    payload = matrix.to_dict()
    assert payload["query_taxon"] == "Streptomyces"
    assert payload["rows"][0]["provenance"]["source_database"] == "synthetic_fixture"
