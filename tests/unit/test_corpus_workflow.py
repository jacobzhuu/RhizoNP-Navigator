from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine

from rhizonp.domain.models import Base
from rhizonp.ingestion.corpus import (
    corpus_snapshot_from_records,
    fetch_domain_corpus,
    load_corpus_query_config,
    load_corpus_snapshot,
    normalized_records_from_snapshot,
    save_corpus_snapshot,
    save_versioned_corpus_snapshot,
    verify_corpus_snapshot_directory,
)
from rhizonp.ingestion.literature import ingest_literature_records
from rhizonp.literature.http_client import HttpResponse
from rhizonp.literature.pubmed_adapter import PubMedEutilitiesAdapter
from rhizonp.storage.postgres import create_session_factory, session_scope
from rhizonp.storage.repositories import PaperRepository

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "pubmed"


class FakeHttpClient:
    def __init__(self, *, esearch_payload: dict, efetch_text: str) -> None:
        self.esearch_payload = esearch_payload
        self.efetch_text = efetch_text

    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        timeout: float,
    ) -> HttpResponse:
        if "esearch.fcgi" in url:
            return HttpResponse(status_code=200, text=json.dumps(self.esearch_payload), url=url)
        if "efetch.fcgi" in url:
            return HttpResponse(status_code=200, text=self.efetch_text, url=url)
        raise AssertionError(url)


def test_fetch_domain_corpus_deduplicates_pmids_and_persists_snapshot(tmp_path: Path) -> None:
    esearch_payload = json.loads((FIXTURE_DIR / "esearch_response.json").read_text(encoding="utf-8"))
    efetch_payload = (FIXTURE_DIR / "efetch_response.xml").read_text(encoding="utf-8")
    adapter = PubMedEutilitiesAdapter(http_client=FakeHttpClient(
        esearch_payload=esearch_payload,
        efetch_text=efetch_payload,
    ))
    config = {
        "corpus_name": "test_corpus",
        "default_retmax": 2,
        "max_total_records": 3,
        "queries": [
            {"query_id": "C001", "term": "Streptomyces rhizosphere"},
            {"query_id": "C002", "term": "Streptomyces rhizosphere"},
        ],
    }

    records, metadata = fetch_domain_corpus(adapter, config)
    snapshot = corpus_snapshot_from_records(records, metadata=metadata)
    output_path = save_corpus_snapshot(snapshot, tmp_path / "corpus.json")

    assert metadata["record_count"] == 2
    assert len(records) == 2
    assert snapshot["metadata"]["metadata_only"] is True
    assert output_path.exists()

    reloaded = load_corpus_snapshot(output_path)
    reloaded_records = normalized_records_from_snapshot(reloaded)
    assert len(reloaded_records) == 2
    assert reloaded_records[0].provenance["full_text"] is False


def test_ingest_pubmed_corpus_snapshot_maps_to_paper_schema() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    snapshot = load_corpus_snapshot(FIXTURE_DIR / "corpus_snapshot.json")
    records = normalized_records_from_snapshot(snapshot)

    with session_scope(session_factory) as session:
        summary = ingest_literature_records(session, records)
        paper = PaperRepository(session).find_by_pmid("12345678")

    assert summary.papers == 1
    assert summary.paper_chunks >= 2
    assert paper is not None
    assert paper.doi == "10.0000/rhizonp.pubmed.fixture.001"
    assert paper.source_url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
    assert paper.provenance["metadata_only"] is True


def test_load_corpus_query_config_reads_domain_queries() -> None:
    config = load_corpus_query_config(
        Path(__file__).resolve().parents[2] / "data" / "eval" / "domain_corpus_queries.json"
    )
    assert config["corpus_name"] == "rhizonp_domain_v1"
    assert config["max_total_records"] == 200
    assert len(config["queries"]) >= 15


def test_versioned_snapshot_roundtrip(tmp_path: Path) -> None:
    esearch_payload = json.loads((FIXTURE_DIR / "esearch_response.json").read_text(encoding="utf-8"))
    efetch_payload = (FIXTURE_DIR / "efetch_response.xml").read_text(encoding="utf-8")
    adapter = PubMedEutilitiesAdapter(http_client=FakeHttpClient(
        esearch_payload=esearch_payload,
        efetch_text=efetch_payload,
    ))
    config = {
        "corpus_id": "test_corpus",
        "corpus_name": "test_corpus",
        "default_retmax": 2,
        "max_total_records": 3,
        "queries": [
            {"query_id": "C001", "term": "Streptomyces rhizosphere"},
        ],
    }
    records, metadata = fetch_domain_corpus(adapter, config)
    snapshot = corpus_snapshot_from_records(records, metadata=metadata)
    corpus_path, manifest_path = save_versioned_corpus_snapshot(
        snapshot,
        tmp_path / "test_snapshot",
    )[:2]
    manifest = verify_corpus_snapshot_directory(corpus_path.parent)
    assert manifest["paper_count"] == metadata["record_count"]
    assert manifest["deduplication_rules"]["key"] == "pmid"
    assert manifest_path.exists()
