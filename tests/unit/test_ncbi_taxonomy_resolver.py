from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhizonp.taxonomy.distance import compute_taxonomy_distance
from rhizonp.taxonomy.fixture_resolver import normalize_taxon_label_from_fixture
from rhizonp.taxonomy.grading import grade_evidence
from rhizonp.taxonomy.models import TaxonomyDistance
from rhizonp.taxonomy.ncbi_resolver import (
    DEFAULT_NCBI_TAXONOMY_CACHE_PATH,
    lookup_cached_ncbi_taxonomy,
    normalize_taxonomy_key,
    parse_taxonomy_xml,
)
from rhizonp.taxonomy.normalization import normalize_taxon_label
from rhizonp.taxonomy.resolvers import TaxonomyResolverMode

SAMPLE_XML = """<?xml version=\"1.0\" ?>
<TaxaSet><Taxon>
    <TaxId>1883</TaxId>
    <ScientificName>Streptomyces</ScientificName>
    <Rank>genus</Rank>
    <Lineage>cellular organisms; Bacteria</Lineage>
    <LineageEx><Taxon><TaxId>2062</TaxId><ScientificName>Streptomycetaceae</ScientificName><Rank>family</Rank></Taxon></LineageEx>
    <OtherNames><Synonym>Chainia</Synonym></OtherNames>
</Taxon></TaxaSet>
"""


def test_parse_taxonomy_xml_extracts_taxid_and_lineage() -> None:
    records = parse_taxonomy_xml(SAMPLE_XML)
    assert len(records) == 1
    assert records[0].taxid == "1883"
    assert records[0].scientific_name == "Streptomyces"
    assert records[0].family == "Streptomycetaceae"
    assert "Chainia" in records[0].synonyms


def test_fixture_mode_unchanged_for_existing_tests() -> None:
    taxon = normalize_taxon_label("Streptomyces hygroscopicus OS-2")
    assert taxon.rank == "strain"
    assert taxon.strain == "OS-2"


def test_ncbi_cached_resolver_returns_real_taxid() -> None:
    if not DEFAULT_NCBI_TAXONOMY_CACHE_PATH.is_file():
        pytest.skip("Committed NCBI taxonomy cache not present.")
    taxon = normalize_taxon_label(
        "Streptomyces",
        resolver_mode=TaxonomyResolverMode.NCBI_CACHED,
    )
    assert taxon.external_ids["ncbi_taxid"] == "1883"
    assert taxon.normalization_status == "resolved_ncbi"
    assert taxon.external_ids["source"] == "ncbi_taxonomy"


def test_ncbi_cached_genus_to_species_distance() -> None:
    if not DEFAULT_NCBI_TAXONOMY_CACHE_PATH.is_file():
        pytest.skip("Committed NCBI taxonomy cache not present.")
    query = lookup_cached_ncbi_taxonomy("Streptomyces")
    literature = lookup_cached_ncbi_taxonomy("Streptomyces hygroscopicus")
    assert query is not None and literature is not None
    distance = compute_taxonomy_distance(query, literature)
    assert distance == TaxonomyDistance.SAME_GENUS


def test_auto_mode_falls_back_to_fixture_for_strain_label() -> None:
    if not DEFAULT_NCBI_TAXONOMY_CACHE_PATH.is_file():
        pytest.skip("Committed NCBI taxonomy cache not present.")
    fixture = normalize_taxon_label_from_fixture("Streptomyces hygroscopicus OS-2")
    auto = normalize_taxon_label(
        "Streptomyces hygroscopicus OS-2",
        resolver_mode=TaxonomyResolverMode.AUTO,
    )
    assert auto.rank == fixture.rank
    assert auto.strain == fixture.strain


def test_ncbi_cached_unknown_label_stays_unresolved() -> None:
    if not DEFAULT_NCBI_TAXONOMY_CACHE_PATH.is_file():
        pytest.skip("Committed NCBI taxonomy cache not present.")
    taxon = normalize_taxon_label(
        "UnknownActinobacterium XYZ",
        resolver_mode=TaxonomyResolverMode.NCBI_CACHED,
    )
    assert taxon.normalization_status == "unresolved"


def test_grade_evidence_with_ncbi_cached_preserves_genus_safety() -> None:
    if not DEFAULT_NCBI_TAXONOMY_CACHE_PATH.is_file():
        pytest.skip("Committed NCBI taxonomy cache not present.")
    result = grade_evidence(
        "Streptomyces",
        "Streptomyces hygroscopicus",
        observation_method="synthetic_16S_fixture",
        resolver_mode=TaxonomyResolverMode.NCBI_CACHED.value,
    )
    assert result.taxonomy_distance == TaxonomyDistance.SAME_GENUS
    assert result.query_taxon.external_ids["ncbi_taxid"] == "1883"
    assert any("strain-level" in warning.lower() for warning in result.warnings)


@pytest.fixture
def tiny_cache(tmp_path: Path) -> Path:
    payload = {
        "metadata": {"real_bounded_ncbi_taxonomy": True},
        "entries": {
            normalize_taxonomy_key("Bacillus subtilis"): {
                "query_label": "Bacillus subtilis",
                "taxid": "1423",
                "scientific_name": "Bacillus subtilis",
                "rank": "species",
                "lineage": "Bacteria; Bacillota",
                "lineage_ex": [],
                "synonyms": [],
                "genus": "Bacillus",
                "species": "Bacillus subtilis",
                "family": "Bacillaceae",
                "provenance": {"source": "ncbi_taxonomy"},
            }
        },
    }
    path = tmp_path / "cache.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_lookup_uses_provided_cache_path(tiny_cache: Path) -> None:
    taxon = lookup_cached_ncbi_taxonomy("Bacillus subtilis", cache_path=tiny_cache)
    assert taxon is not None
    assert taxon.external_ids["ncbi_taxid"] == "1423"
