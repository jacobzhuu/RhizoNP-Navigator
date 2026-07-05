from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhizonp.ingestion.npatlas import RawNPAtlasRecord, normalize_npatlas_record
from rhizonp.ingestion.npatlas_bioactivity import derive_structured_bioactivity
from rhizonp.linking.candidate_engine import _build_row, link_natural_product_candidates
from rhizonp.linking.models import BioactivityRecord, NaturalProductFixtureRecord
from rhizonp.linking.np_adapter import NaturalProductSource, load_bounded_npatlas_records


@pytest.fixture
def npatlas_snapshot_path(tmp_path: Path) -> Path:
    snapshot = {
        "metadata": {
            "snapshot_id": "test_snapshot",
            "real_bounded_npatlas": True,
            "not_synthetic_fixture": True,
        },
        "records": [
            {
                "npaid": "NPA000037",
                "compound_name": "Lajollamycin",
                "producer_taxon": "nodosus (NPS007994)",
                "producer_genus": "Streptomyces",
                "producer_species": "nodosus (NPS007994)",
                "source_database": "npatlas",
                "external_record_id": "NPA000037",
                "inchikey": "NSTDWVVCICGULY-RLJWGYAPSA-N",
                "origin_reference": {
                    "doi": "10.1021/np049725x",
                    "pmid": 15730252,
                    "title": "Lajollamycin, a nitro-tetraene spiro-β-lactone-γ-lactam antibiotic from the marine actinomycete Streptomyces nodosus",
                },
                "origin_organism": {
                    "genus": "Streptomyces",
                    "species": "nodosus (NPS007994)",
                    "ncbi_id": 1883,
                    "taxon_rank": "genus",
                },
                "provenance": {
                    "source": "npatlas_api",
                    "real_bounded_snapshot": True,
                    "not_synthetic_fixture": True,
                },
            }
        ],
    }
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    return path


def test_derive_structured_bioactivity_from_inhibitor_title() -> None:
    payload = derive_structured_bioactivity(
        npaid="NPA000003",
        origin_reference={
            "title": "A-503083 A, B, E and F, novel inhibitors of bacterial translocase i",
            "doi": "10.7164/antibiotics.57.639",
        },
        source_url="https://www.npatlas.org/explore/compounds/NPA000003",
    )
    assert payload is not None
    assert payload["activity_type"] == "inhibitor"
    assert payload["evidence_level"] == "origin_reference_reported"
    assert payload["provenance"]["real_bounded_npatlas"] is True


def test_derive_structured_bioactivity_from_active_against_title() -> None:
    payload = derive_structured_bioactivity(
        npaid="NPA000024",
        origin_reference={
            "title": "Anisomycin and new congeners active against human tumor cell lines",
        },
        source_url="https://www.npatlas.org/explore/compounds/NPA000024",
    )
    assert payload is not None
    assert payload["activity_type"] == "active_against"
    assert payload["target"] == "human tumor cell lines"


def test_normalize_npatlas_record_attaches_bioactivity() -> None:
    normalized = normalize_npatlas_record(
        RawNPAtlasRecord(
            npaid="NPA000055",
            compound_name="Oxachelin",
            producer_taxon="Streptomyces sp. GW9/1258",
            origin_reference={
                "title": "Oxachelin, a novel iron chelator and antifungal agent from Streptomyces sp. GW9/1258",
                "doi": "10.1038/ja.2006.88",
            },
        )
    )
    assert normalized.bioactivity is not None
    assert normalized.bioactivity["activity_type"] in {"antifungal", "iron_chelator"}
    assert normalized.bioactivity_summary is not None


def test_npatlas_fixture_records_include_bioactivity(npatlas_snapshot_path: Path) -> None:
    load_bounded_npatlas_records.cache_clear()
    records = load_bounded_npatlas_records(npatlas_snapshot_path)
    assert records
    assert all(record.bioactivity is not None for record in records)


def test_bioactivity_metadata_does_not_change_candidate_score() -> None:
    base = NaturalProductFixtureRecord(
        key="npatlas_npa000037",
        compound_name="Lajollamycin",
        producer_taxon="Streptomyces nodosus (NPS007994)",
        source_database="npatlas",
        external_record_id="NPA000037",
        bioactivity=None,
        provenance={"source": "npatlas", "external_record_id": "NPA000037"},
    )
    with_bio = NaturalProductFixtureRecord(
        key=base.key,
        compound_name=base.compound_name,
        producer_taxon=base.producer_taxon,
        source_database=base.source_database,
        external_record_id=base.external_record_id,
        bioactivity=BioactivityRecord(
            activity_type="antibacterial",
            target=None,
            evidence_level="origin_reference_reported",
        ),
        provenance=base.provenance,
    )
    row_without = _build_row(
        query_taxon="Streptomyces",
        record=base,
        normalized_metabolite=None,
        observation_method="synthetic_16S_fixture",
    )
    row_with = _build_row(
        query_taxon="Streptomyces",
        record=with_bio,
        normalized_metabolite=None,
        observation_method="synthetic_16S_fixture",
    )
    assert row_without.bioactivity is None
    assert row_with.bioactivity is not None
    assert row_without.score == row_with.score


def test_link_candidates_surface_npatlas_bioactivity(npatlas_snapshot_path: Path) -> None:
    load_bounded_npatlas_records.cache_clear()
    matrix = link_natural_product_candidates(
        "Streptomyces",
        observation_method="synthetic_16S_fixture",
        record_source=NaturalProductSource.NPATLAS_BOUNDED,
        snapshot_path=str(npatlas_snapshot_path),
    )
    assert matrix.rows
    assert matrix.rows[0].bioactivity is not None
    assert matrix.rows[0].bioactivity["activity_type"] == "antibacterial"


def test_committed_snapshot_bioactivity_coverage_if_present() -> None:
    from rhizonp.ingestion.npatlas import DEFAULT_NPATLAS_SNAPSHOT_PATH

    if not DEFAULT_NPATLAS_SNAPSHOT_PATH.is_file():
        pytest.skip("Committed NPAtlas bounded snapshot not present locally.")
    load_bounded_npatlas_records.cache_clear()
    records = load_bounded_npatlas_records()
    assert len(records) >= 10
    assert all(record.bioactivity is not None for record in records)
    assert all(record.provenance.get("bioactivity_summary") for record in records)
