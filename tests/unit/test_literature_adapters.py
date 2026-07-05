from __future__ import annotations

from rhizonp.literature.adapters import (
    RawLiteratureRecord,
    SyntheticLiteratureAdapter,
    raw_literature_record_from_mapping,
)


def _fixture_record() -> RawLiteratureRecord:
    return raw_literature_record_from_mapping(
        {
            "source_id": "fixture-lit-001",
            "title": "Synthetic Streptomyces rhizosphere paper",
            "abstract": "Genus-level Streptomyces observations in a synthetic rhizosphere context.",
            "sections": {
                "results": "Feature_M123 co-occurs with Streptomyces at genus level only.",
            },
            "doi": "10.0000/rhizonp.fixture.lit.001",
            "year": 2025,
            "journal": "Fixture Journal",
            "source_url": "https://example.org/rhizonp/fixture-literature-001",
            "metadata": {
                "source_type": "paper",
                "taxa": ["Streptomyces"],
                "compounds": ["FixturePolyketide-A"],
            },
        }
    )


def test_synthetic_adapter_fetch_returns_all_records_for_empty_query() -> None:
    record = _fixture_record()
    adapter = SyntheticLiteratureAdapter([record])

    fetched = adapter.fetch({})

    assert fetched == [record]


def test_synthetic_adapter_fetch_filters_by_query_terms() -> None:
    record = _fixture_record()
    adapter = SyntheticLiteratureAdapter([record])

    matched = adapter.fetch({"query": "Streptomyces genus"})
    unmatched = adapter.fetch({"query": "Bacillus isolate"})

    assert matched == [record]
    assert unmatched == []


def test_synthetic_adapter_normalize_and_provenance_mark_fixture_boundary() -> None:
    record = _fixture_record()
    adapter = SyntheticLiteratureAdapter([record])

    normalized = adapter.normalize(record)
    provenance = adapter.provenance(record)

    assert normalized.source_name == "synthetic_fixture"
    assert normalized.doi == "10.0000/rhizonp.fixture.lit.001"
    assert normalized.provenance["fixture"] is True
    assert provenance["not_real_literature"] is True
    assert provenance["source_id"] == "fixture-lit-001"
