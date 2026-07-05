from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from rhizonp.config import Settings, get_settings
from rhizonp.literature.adapters import NormalizedLiteratureRecord, RawLiteratureRecord
from rhizonp.literature.http_client import HttpClient, UrllibHttpClient

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ESEARCH_URL = f"{EUTILS_BASE}/esearch.fcgi"
EFETCH_URL = f"{EUTILS_BASE}/efetch.fcgi"
PUBMED_ARTICLE_URL = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
NCBI_POLICY_URL = "https://www.ncbi.nlm.nih.gov/home/about/policies/"


class PubMedAdapterError(RuntimeError):
    """Base error for PubMed E-utilities adapter failures."""


class PubMedSearchError(PubMedAdapterError):
    """Raised when PMID search fails."""


class PubMedFetchError(PubMedAdapterError):
    """Raised when record fetch fails."""


class PubMedParseError(PubMedAdapterError):
    """Raised when PubMed XML cannot be parsed."""


@dataclass(frozen=True)
class PubMedFetchContext:
    query: Mapping[str, Any]
    fetched_at: str
    pmids: tuple[str, ...]
    retmax: int


class PubMedEutilitiesAdapter:
    """Fetch PubMed metadata (title/abstract) via NCBI E-utilities.

    This adapter does not download copyrighted full text. It maps conservative
    metadata into ``RawLiteratureRecord`` for downstream Paper ingestion.
    """

    source_name = "pubmed_eutils"

    def __init__(
        self,
        *,
        tool_name: str | None = None,
        contact_email: str | None = None,
        api_key: str | None = None,
        request_timeout: float | None = None,
        max_results: int | None = None,
        http_client: HttpClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved = settings or get_settings()
        self.tool_name = tool_name or resolved.ncbi_tool_name
        self.contact_email = contact_email or resolved.ncbi_email
        self.api_key = api_key or resolved.ncbi_api_key
        self.request_timeout = request_timeout or resolved.ncbi_request_timeout
        self.max_results = max_results or resolved.ncbi_max_results
        self._http_client = http_client or UrllibHttpClient()
        self._last_fetch_context: PubMedFetchContext | None = None

    @property
    def last_fetch_context(self) -> PubMedFetchContext | None:
        return self._last_fetch_context

    def fetch(self, query: Mapping[str, Any]) -> list[RawLiteratureRecord]:
        term = str(query.get("query") or query.get("term") or "").strip()
        if not term:
            return []

        retmax = int(query.get("retmax", self.max_results))
        if retmax <= 0:
            return []
        retmax = min(retmax, self.max_results)

        pmids = self._search_pmids(term, retmax=retmax, query=query)
        self._last_fetch_context = PubMedFetchContext(
            query=dict(query),
            fetched_at=datetime.now(tz=timezone.utc).isoformat(),
            pmids=tuple(pmids),
            retmax=retmax,
        )
        if not pmids:
            return []

        xml_payload = self._fetch_pubmed_xml(pmids)
        records = parse_pubmed_xml(xml_payload)
        return [
            RawLiteratureRecord(
                source_id=record["source_id"],
                title=record["title"],
                abstract=record.get("abstract"),
                doi=record.get("doi"),
                pmid=record.get("pmid"),
                pmcid=record.get("pmcid"),
                year=record.get("year"),
                journal=record.get("journal"),
                source_url=record.get("source_url"),
                license="metadata_only",
                metadata={
                    **record.get("metadata", {}),
                    "pubmed_fetch_context": {
                        "query": dict(query),
                        "fetched_at": self._last_fetch_context.fetched_at,
                        "retmax": retmax,
                    },
                },
            )
            for record in records
        ]

    def normalize(self, record: RawLiteratureRecord) -> NormalizedLiteratureRecord:
        return NormalizedLiteratureRecord(
            source_id=record.source_id,
            source_name=self.source_name,
            title=record.title,
            abstract=record.abstract,
            sections=dict(record.sections),
            doi=record.doi,
            pmid=record.pmid,
            pmcid=record.pmcid,
            year=record.year,
            journal=record.journal,
            source_url=record.source_url,
            license=record.license,
            metadata=dict(record.metadata),
            provenance=self.provenance(record),
        )

    def provenance(self, record: RawLiteratureRecord) -> dict[str, Any]:
        fetch_context = record.metadata.get("pubmed_fetch_context", {})
        return {
            "source_name": self.source_name,
            "source_id": record.source_id,
            "pmid": record.pmid,
            "doi": record.doi,
            "fixture": False,
            "not_real_literature": False,
            "metadata_only": True,
            "full_text": False,
            "api": "NCBI E-utilities",
            "policy_url": NCBI_POLICY_URL,
            "fetched_at": fetch_context.get("fetched_at"),
            "query": fetch_context.get("query"),
            "tool_name": self.tool_name,
            "contact_email": self.contact_email or None,
        }

    def _base_params(self) -> dict[str, str]:
        params = {
            "tool": self.tool_name,
        }
        if self.contact_email:
            params["email"] = self.contact_email
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def _search_pmids(
        self,
        term: str,
        *,
        retmax: int,
        query: Mapping[str, Any],
    ) -> list[str]:
        params = {
            **self._base_params(),
            "db": "pubmed",
            "term": term,
            "retmax": str(retmax),
            "retmode": "json",
        }
        mindate = query.get("mindate")
        maxdate = query.get("maxdate")
        if mindate:
            params["mindate"] = str(mindate)
        if maxdate:
            params["maxdate"] = str(maxdate)

        try:
            response = self._http_client.get(
                ESEARCH_URL,
                params=params,
                timeout=self.request_timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except TimeoutError as exc:
            raise PubMedSearchError(f"PubMed esearch timed out for term {term!r}.") from exc
        except json.JSONDecodeError as exc:
            raise PubMedSearchError("PubMed esearch returned non-JSON payload.") from exc
        except Exception as exc:
            if isinstance(exc, PubMedAdapterError):
                raise
            raise PubMedSearchError(f"PubMed esearch failed for term {term!r}: {exc}") from exc

        id_list = payload.get("esearchresult", {}).get("idlist", [])
        if not isinstance(id_list, list):
            raise PubMedSearchError("PubMed esearch returned malformed idlist.")
        return [str(pmid) for pmid in id_list if str(pmid).strip()]

    def _fetch_pubmed_xml(self, pmids: list[str]) -> str:
        params = {
            **self._base_params(),
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }
        try:
            response = self._http_client.get(
                EFETCH_URL,
                params=params,
                timeout=self.request_timeout,
            )
            response.raise_for_status()
            return response.text
        except TimeoutError as exc:
            raise PubMedFetchError("PubMed efetch timed out.") from exc
        except Exception as exc:
            if isinstance(exc, PubMedAdapterError):
                raise
            raise PubMedFetchError(f"PubMed efetch failed: {exc}") from exc


def parse_pubmed_xml(xml_payload: str) -> list[dict[str, Any]]:
    if not xml_payload.strip():
        return []

    try:
        root = ET.fromstring(xml_payload)
    except ET.ParseError as exc:
        raise PubMedParseError("PubMed XML payload is not well-formed.") from exc

    records: list[dict[str, Any]] = []
    for article in root.findall(".//PubmedArticle"):
        parsed = _parse_pubmed_article(article)
        if parsed is not None:
            records.append(parsed)
    return records


def _parse_pubmed_article(article: ET.Element) -> dict[str, Any] | None:
    pmid = _element_text(article, ".//MedlineCitation/PMID")
    if not pmid:
        return None

    title = _element_text(article, ".//ArticleTitle") or f"PubMed record {pmid}"
    abstract = _collect_abstract_text(article)
    journal = _element_text(article, ".//Journal/Title")
    year = _parse_year(article)
    doi = _find_article_id(article, "doi")
    pmcid = _find_article_id(article, "pmc")

    return {
        "source_id": pmid,
        "pmid": pmid,
        "title": title.strip(),
        "abstract": abstract,
        "doi": doi,
        "pmcid": pmcid,
        "year": year,
        "journal": journal,
        "source_url": PUBMED_ARTICLE_URL.format(pmid=pmid),
        "metadata": {
            "source_type": "paper",
            "pubmed_record": True,
        },
    }


def _collect_abstract_text(article: ET.Element) -> str | None:
    abstract_root = article.find(".//Abstract")
    if abstract_root is None:
        return None

    parts: list[str] = []
    for abstract_text in abstract_root.findall("AbstractText"):
        label = abstract_text.attrib.get("Label")
        text = "".join(abstract_text.itertext()).strip()
        if not text:
            continue
        if label:
            parts.append(f"{label}: {text}")
        else:
            parts.append(text)
    if not parts:
        return None
    return "\n\n".join(parts)


def _parse_year(article: ET.Element) -> int | None:
    year_text = _element_text(article, ".//PubDate/Year")
    if year_text and year_text.isdigit():
        return int(year_text)
    medline_date = _element_text(article, ".//PubDate/MedlineDate")
    if medline_date:
        token = medline_date.split()[0]
        if token.isdigit() and len(token) == 4:
            return int(token)
    return None


def _find_article_id(article: ET.Element, id_type: str) -> str | None:
    for article_id in article.findall(".//ArticleId"):
        if article_id.attrib.get("IdType") == id_type:
            value = (article_id.text or "").strip()
            if value:
                return value
    return None


def _element_text(element: ET.Element, path: str) -> str | None:
    found = element.find(path)
    if found is None or found.text is None:
        return None
    return found.text.strip()
