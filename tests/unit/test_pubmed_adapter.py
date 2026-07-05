from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhizonp.config import Settings
from rhizonp.literature.http_client import HttpResponse
from rhizonp.literature.pubmed_adapter import (
    PubMedEutilitiesAdapter,
    PubMedFetchError,
    PubMedParseError,
    PubMedSearchError,
    parse_pubmed_xml,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "pubmed"


class FakeHttpClient:
    def __init__(
        self,
        *,
        esearch_payload: dict | None = None,
        efetch_text: str | None = None,
        status_code: int = 200,
        fail_on: str | None = None,
    ) -> None:
        self.esearch_payload = esearch_payload
        self.efetch_text = efetch_text
        self.status_code = status_code
        self.fail_on = fail_on
        self.requests: list[tuple[str, dict[str, str] | None]] = []

    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        timeout: float,
    ) -> HttpResponse:
        self.requests.append((url, params))
        if self.fail_on == "timeout":
            raise TimeoutError("timed out")
        if self.fail_on == "esearch" and "esearch.fcgi" in url:
            return HttpResponse(status_code=500, text="server error", url=url)
        if self.fail_on == "efetch" and "efetch.fcgi" in url:
            return HttpResponse(status_code=503, text="unavailable", url=url)

        if "esearch.fcgi" in url:
            payload = self.esearch_payload or {}
            return HttpResponse(
                status_code=self.status_code,
                text=json.dumps(payload),
                url=url,
            )
        if "efetch.fcgi" in url:
            return HttpResponse(
                status_code=self.status_code,
                text=self.efetch_text or "",
                url=url,
            )
        raise AssertionError(f"Unexpected URL: {url}")


def test_parse_pubmed_xml_maps_metadata_and_skips_malformed_records() -> None:
    xml_payload = (FIXTURE_DIR / "efetch_response.xml").read_text(encoding="utf-8")

    records = parse_pubmed_xml(xml_payload)

    assert len(records) == 2
    first = records[0]
    assert first["pmid"] == "12345678"
    assert first["doi"] == "10.0000/rhizonp.pubmed.fixture.001"
    assert first["year"] == 2024
    assert first["journal"] == "Fixture Journal of Plant Microbe Interactions"
    assert "Streptomyces" in first["abstract"]
    assert first["source_url"] == "https://pubmed.ncbi.nlm.nih.gov/12345678/"

    second = records[1]
    assert second["pmid"] == "87654321"
    assert second["year"] == 2023
    assert second["abstract"] is None


def test_pubmed_adapter_fetch_uses_mocked_http_and_preserves_provenance() -> None:
    esearch_payload = json.loads((FIXTURE_DIR / "esearch_response.json").read_text(encoding="utf-8"))
    efetch_payload = (FIXTURE_DIR / "efetch_response.xml").read_text(encoding="utf-8")
    client = FakeHttpClient(esearch_payload=esearch_payload, efetch_text=efetch_payload)
    adapter = PubMedEutilitiesAdapter(
        tool_name="RhizoNP-Navigator-Test",
        contact_email="test@example.org",
        http_client=client,
        settings=Settings(ncbi_max_results=10, ncbi_request_timeout=5.0),
    )

    raw_records = adapter.fetch({"query": "Streptomyces rhizosphere", "retmax": 2})
    normalized = [adapter.normalize(record) for record in raw_records]

    assert len(raw_records) == 2
    assert raw_records[0].pmid == "12345678"
    assert raw_records[0].license == "metadata_only"
    assert normalized[0].source_name == "pubmed_eutils"
    provenance = adapter.provenance(raw_records[0])
    assert provenance["metadata_only"] is True
    assert provenance["full_text"] is False
    assert provenance["api"] == "NCBI E-utilities"
    assert provenance["query"]["query"] == "Streptomyces rhizosphere"
    assert adapter.last_fetch_context is not None
    assert adapter.last_fetch_context.pmids == ("12345678", "87654321")

    esearch_request = next(params for url, params in client.requests if "esearch.fcgi" in url)
    assert esearch_request is not None
    assert esearch_request["tool"] == "RhizoNP-Navigator-Test"
    assert esearch_request["email"] == "test@example.org"
    assert esearch_request["term"] == "Streptomyces rhizosphere"


def test_pubmed_adapter_returns_empty_list_for_empty_query_and_search() -> None:
    adapter = PubMedEutilitiesAdapter(http_client=FakeHttpClient())
    assert adapter.fetch({"query": ""}) == []

    client = FakeHttpClient(esearch_payload={"esearchresult": {"idlist": []}})
    adapter = PubMedEutilitiesAdapter(http_client=client)
    assert adapter.fetch({"query": "no matches"}) == []


def test_pubmed_adapter_raises_on_http_and_timeout_errors() -> None:
    adapter = PubMedEutilitiesAdapter(
        http_client=FakeHttpClient(fail_on="esearch"),
        settings=Settings(ncbi_request_timeout=1.0),
    )
    with pytest.raises(PubMedSearchError):
        adapter.fetch({"query": "Streptomyces"})

    esearch_payload = json.loads((FIXTURE_DIR / "esearch_response.json").read_text(encoding="utf-8"))
    adapter = PubMedEutilitiesAdapter(
        http_client=FakeHttpClient(esearch_payload=esearch_payload, fail_on="efetch"),
    )
    with pytest.raises(PubMedFetchError):
        adapter.fetch({"query": "Streptomyces"})

    adapter = PubMedEutilitiesAdapter(http_client=FakeHttpClient(fail_on="timeout"))
    with pytest.raises(PubMedSearchError):
        adapter.fetch({"query": "Streptomyces"})


def test_parse_pubmed_xml_raises_on_invalid_xml() -> None:
    with pytest.raises(PubMedParseError):
        parse_pubmed_xml("<PubmedArticleSet><unclosed>")
