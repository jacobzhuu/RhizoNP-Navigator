from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhizonp.ingestion.npatlas import (
    NPAtlasHttpAdapter,
    RawNPAtlasRecord,
    normalize_npatlas_record,
)
from rhizonp.linking.candidate_engine import link_natural_product_candidates
from rhizonp.linking.np_adapter import (
    NaturalProductSource,
    load_bounded_npatlas_records,
    load_natural_product_records,
)
from rhizonp.literature.http_client import HttpResponse


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
                "origin_reference": {"doi": "10.1021/np049725x", "pmid": 15730252},
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


def test_normalize_npatlas_record_prefixes_genus_for_producer() -> None:
    normalized = normalize_npatlas_record(
        RawNPAtlasRecord(
            npaid="NPA000037",
            compound_name="Lajollamycin",
            producer_taxon="nodosus (NPS007994)",
            producer_genus="Streptomyces",
            producer_species="nodosus (NPS007994)",
        )
    )
    assert normalized.producer_taxon.startswith("Streptomyces")
    assert normalized.source_database == "npatlas"
    assert normalized.provenance["not_synthetic_fixture"] is True


def test_load_bounded_npatlas_snapshot(tmp_path: Path, npatlas_snapshot_path: Path) -> None:
    load_bounded_npatlas_records.cache_clear()
    records = load_bounded_npatlas_records(npatlas_snapshot_path)
    assert len(records) == 1
    assert records[0].external_record_id == "NPA000037"
    assert records[0].source_database == "npatlas"
    assert records[0].provenance["not_synthetic_fixture"] is True


def test_link_candidates_with_npatlas_bounded_source(
    npatlas_snapshot_path: Path,
) -> None:
    load_bounded_npatlas_records.cache_clear()
    matrix = link_natural_product_candidates(
        "Streptomyces",
        observation_method="synthetic_16S_fixture",
        record_source=NaturalProductSource.NPATLAS_BOUNDED,
        snapshot_path=str(npatlas_snapshot_path),
    )
    assert matrix.rows
    top = matrix.rows[0]
    assert top.provenance["source_database"] == "npatlas"
    assert top.provenance["external_record_id"] == "NPA000037"
    assert top.evidence_tier in {"B", "C"}


def test_npatlas_http_adapter_fetch_uses_post_with_mock_client() -> None:
    calls: list[tuple[str, str]] = []

    class MockClient:
        def get(self, url: str, *, params=None, timeout: float) -> HttpResponse:
            calls.append(("GET", url))
            assert "NPA000003" in url
            return HttpResponse(
                status_code=200,
                text=json.dumps(
                    {
                        "npaid": "NPA000003",
                        "original_name": "A-503083 F",
                        "origin_organism": {
                            "genus": "Streptomyces",
                            "species": "sp. SANK 62799",
                            "taxon": {"name": "Streptomyces", "ncbi_id": 1883, "rank": "genus"},
                        },
                        "origin_reference": {"doi": "10.7164/antibiotics.57.639"},
                    }
                ),
                url=url,
            )

        def post(self, url: str, *, params=None, timeout: float) -> HttpResponse:
            calls.append(("POST", url))
            return HttpResponse(
                status_code=200,
                text=json.dumps([{"npaid": "NPA000003", "original_name": "A-503083 F"}]),
                url=url,
            )

    adapter = NPAtlasHttpAdapter(http_client=MockClient())
    records = adapter.fetch({"taxon": "Streptomyces", "rank": "genus", "limit": 1})
    assert len(records) == 1
    assert records[0].npaid == "NPA000003"
    assert any(method == "POST" for method, _ in calls)


def test_committed_npatlas_snapshot_loads_if_present() -> None:
    from rhizonp.ingestion.npatlas import DEFAULT_NPATLAS_SNAPSHOT_PATH

    if not DEFAULT_NPATLAS_SNAPSHOT_PATH.is_file():
        pytest.skip("Committed NPAtlas bounded snapshot not present locally.")
    records = load_natural_product_records(source=NaturalProductSource.NPATLAS_BOUNDED)
    assert len(records) >= 10
    assert all(record.source_database == "npatlas" for record in records)
    assert all(record.provenance.get("not_synthetic_fixture") for record in records)
