from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from rhizonp.domain.models import Paper


class CorpusType(str, Enum):
    REAL_BOUNDED_PUBMED = "REAL_BOUNDED_PUBMED"
    FIXTURE_TEST_ONLY = "FIXTURE_TEST_ONLY"
    SYNTHETIC = "SYNTHETIC"
    UNKNOWN = "UNKNOWN"


def _is_fixture_doi(doi: str | None) -> bool:
    if not doi:
        return False
    normalized = doi.casefold()
    return normalized.startswith("10.0000/") or "rhizonp.fixture" in normalized


def _is_pubmed_source_url(source_url: str | None) -> bool:
    if not source_url:
        return False
    return "pubmed.ncbi.nlm.nih.gov" in source_url.casefold()


def classify_record_entry(entry: Mapping[str, Any]) -> CorpusType:
    """Classify a corpus snapshot record before ingestion."""
    provenance = dict(entry.get("provenance", {}))
    if provenance.get("fixture") is True or provenance.get("not_real_literature") is True:
        return CorpusType.FIXTURE_TEST_ONLY

    source_name = str(entry.get("source_name") or provenance.get("source_name") or "")
    if source_name == "synthetic_fixture":
        return CorpusType.SYNTHETIC

    journal = str(entry.get("journal") or "")
    if journal.casefold() == "fixture":
        return CorpusType.FIXTURE_TEST_ONLY

    source_url = str(entry.get("source_url") or "")
    if "example.org" in source_url.casefold():
        return CorpusType.FIXTURE_TEST_ONLY

    if _is_fixture_doi(entry.get("doi")):
        return CorpusType.FIXTURE_TEST_ONLY

    pmid = entry.get("pmid")
    if source_name == "pubmed_eutils" and pmid and _is_pubmed_source_url(source_url):
        return CorpusType.REAL_BOUNDED_PUBMED

    if pmid and _is_pubmed_source_url(source_url) and not _is_fixture_doi(entry.get("doi")):
        return CorpusType.REAL_BOUNDED_PUBMED

    return CorpusType.UNKNOWN


def classify_paper(paper: Paper | None) -> CorpusType:
    """Classify an ingested paper using persisted provenance and identifiers."""
    if paper is None:
        return CorpusType.UNKNOWN

    provenance = paper.provenance or {}
    if provenance.get("fixture") is True or provenance.get("not_real_literature") is True:
        return CorpusType.FIXTURE_TEST_ONLY

    source_name = str(provenance.get("source_name") or "")
    if source_name == "synthetic_fixture":
        return CorpusType.SYNTHETIC

    if paper.journal and paper.journal.casefold() == "fixture":
        return CorpusType.FIXTURE_TEST_ONLY

    if paper.source_url and "example.org" in paper.source_url.casefold():
        return CorpusType.FIXTURE_TEST_ONLY

    if _is_fixture_doi(paper.doi):
        return CorpusType.FIXTURE_TEST_ONLY

    if source_name == "pubmed_eutils" and paper.pmid and _is_pubmed_source_url(paper.source_url):
        return CorpusType.REAL_BOUNDED_PUBMED

    if paper.pmid and _is_pubmed_source_url(paper.source_url) and not _is_fixture_doi(paper.doi):
        return CorpusType.REAL_BOUNDED_PUBMED

    return CorpusType.UNKNOWN


def infer_corpus_identity_from_snapshot(snapshot: Mapping[str, Any]) -> tuple[CorpusType, str]:
    metadata = dict(snapshot.get("metadata", {}))
    corpus_id = str(metadata.get("corpus_id") or metadata.get("corpus_name") or "unknown")
    records = list(snapshot.get("record", snapshot.get("records", [])))
    if not records:
        return CorpusType.UNKNOWN, corpus_id

    types = {classify_record_entry(record) for record in records}
    if types == {CorpusType.REAL_BOUNDED_PUBMED}:
        return CorpusType.REAL_BOUNDED_PUBMED, corpus_id
    if CorpusType.REAL_BOUNDED_PUBMED in types and CorpusType.FIXTURE_TEST_ONLY not in types:
        return CorpusType.REAL_BOUNDED_PUBMED, corpus_id
    if types <= {CorpusType.FIXTURE_TEST_ONLY, CorpusType.SYNTHETIC}:
        if CorpusType.SYNTHETIC in types:
            return CorpusType.SYNTHETIC, corpus_id
        return CorpusType.FIXTURE_TEST_ONLY, corpus_id
    if CorpusType.REAL_BOUNDED_PUBMED in types:
        return CorpusType.REAL_BOUNDED_PUBMED, corpus_id
    return CorpusType.UNKNOWN, corpus_id
