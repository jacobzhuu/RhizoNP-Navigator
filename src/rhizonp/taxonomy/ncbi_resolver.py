from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from rhizonp.config import PROJECT_ROOT, Settings, get_settings
from rhizonp.literature.http_client import HttpClient, UrllibHttpClient
from rhizonp.taxonomy.models import NormalizedTaxon

NCBI_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_TAXONOMY_POLICY_URL = "https://www.ncbi.nlm.nih.gov/home/about/policies/"
DEFAULT_NCBI_TAXONOMY_CACHE_PATH = (
    PROJECT_ROOT / "data" / "snapshots" / "taxonomy" / "ncbi_bounded_v1" / "cache.json"
)
DEFAULT_BOUNDED_TAXONOMY_QUERIES = (
    "Streptomyces",
    "Streptomyces hygroscopicus",
    "Bacillus subtilis",
    "Bacillus",
)


class NCBITaxonomyError(RuntimeError):
    """Base error for NCBI taxonomy resolver failures."""


@dataclass(frozen=True)
class NCBITaxonomyRecord:
    taxid: str
    scientific_name: str
    rank: str
    lineage: str | None = None
    lineage_ex: list[dict[str, str | None]] = field(default_factory=list)
    synonyms: list[str] = field(default_factory=list)
    genus: str | None = None
    species: str | None = None
    family: str | None = None
    query_label: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


def normalize_taxonomy_key(label: str) -> str:
    cleaned = re.sub(r"\s+", " ", label.strip().lower())
    return cleaned.replace("spp.", "sp.")


def _rank_to_fields(record: NCBITaxonomyRecord) -> dict[str, str | None]:
    rank = (record.rank or "").lower()
    genus = record.genus
    species = record.species
    family = record.family
    strain = None

    if rank == "genus" and genus is None:
        genus = record.scientific_name
    elif rank == "species":
        species = record.scientific_name
        genus = genus or (record.scientific_name.split()[0] if record.scientific_name else None)
    elif rank in {"strain", "isolate"}:
        strain = record.scientific_name.split()[-1] if record.scientific_name else None
        species = species or " ".join(record.scientific_name.split()[:-1]) if record.scientific_name else None
        genus = genus or (record.scientific_name.split()[0] if record.scientific_name else None)

    return {
        "rank": rank or None,
        "genus": genus,
        "species": species,
        "family": family,
        "strain": strain,
    }


def ncbi_record_to_normalized_taxon(record: NCBITaxonomyRecord) -> NormalizedTaxon:
    fields = _rank_to_fields(record)
    return NormalizedTaxon(
        canonical_name=record.scientific_name,
        rank=fields["rank"],
        strain=fields["strain"],
        species=fields["species"],
        genus=fields["genus"],
        family=fields["family"],
        external_ids={
            "ncbi_taxid": record.taxid,
            "lineage": record.lineage,
            "lineage_ex": record.lineage_ex,
            "synonyms": record.synonyms,
            "source": "ncbi_taxonomy",
            "resolver": "ncbi_cached",
        },
        normalization_status="resolved_ncbi",
        confidence=0.95,
    )


def parse_taxonomy_xml(xml_text: str) -> list[NCBITaxonomyRecord]:
    root = ET.fromstring(xml_text)
    records: list[NCBITaxonomyRecord] = []
    for elem in root.findall("Taxon"):
        taxid = elem.findtext("TaxId")
        scientific_name = elem.findtext("ScientificName")
        if not taxid or not scientific_name:
            continue
        lineage_ex: list[dict[str, str | None]] = []
        family = None
        for taxon in elem.findall("./LineageEx/Taxon"):
            item = {
                "taxid": taxon.findtext("TaxId"),
                "scientific_name": taxon.findtext("ScientificName"),
                "rank": taxon.findtext("Rank"),
            }
            lineage_ex.append(item)
            if item["rank"] == "family":
                family = item["scientific_name"]
        rank = (elem.findtext("Rank") or "").lower()
        genus = scientific_name if rank == "genus" else None
        species = scientific_name if rank == "species" else None
        if rank == "species" and genus is None:
            genus = scientific_name.split()[0]
        synonyms = [
            node.text.strip()
            for node in elem.findall("./OtherNames/Synonym")
            if node.text and node.text.strip()
        ]
        records.append(
            NCBITaxonomyRecord(
                taxid=taxid,
                scientific_name=scientific_name,
                rank=rank,
                lineage=elem.findtext("Lineage"),
                lineage_ex=lineage_ex,
                synonyms=synonyms[:20],
                genus=genus,
                species=species,
                family=family,
                provenance={
                    "source": "ncbi_taxonomy",
                    "api_base": NCBI_EUTILS_BASE,
                    "license": "NCBI public domain",
                    "policy_url": NCBI_TAXONOMY_POLICY_URL,
                    "real_bounded_cache": True,
                    "not_synthetic_fixture": True,
                },
            )
        )
    return records


@lru_cache
def load_ncbi_taxonomy_cache(
    cache_path: str | Path = DEFAULT_NCBI_TAXONOMY_CACHE_PATH,
) -> dict[str, NCBITaxonomyRecord]:
    path = Path(cache_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata = payload.get("metadata") or {}
    if not metadata.get("real_bounded_ncbi_taxonomy"):
        raise ValueError(f"NCBI taxonomy cache at {path} is not marked as a real bounded cache.")

    records: dict[str, NCBITaxonomyRecord] = {}
    for key, item in (payload.get("entries") or {}).items():
        records[key] = NCBITaxonomyRecord(
            taxid=str(item["taxid"]),
            scientific_name=str(item["scientific_name"]),
            rank=str(item.get("rank") or ""),
            lineage=item.get("lineage"),
            lineage_ex=list(item.get("lineage_ex") or []),
            synonyms=list(item.get("synonyms") or []),
            genus=item.get("genus"),
            species=item.get("species"),
            family=item.get("family"),
            query_label=item.get("query_label"),
            provenance=dict(item.get("provenance") or {}),
        )
    return records


def lookup_cached_ncbi_taxonomy(
    label: str,
    *,
    cache_path: str | Path = DEFAULT_NCBI_TAXONOMY_CACHE_PATH,
) -> NormalizedTaxon | None:
    cache = load_ncbi_taxonomy_cache(cache_path)
    record = cache.get(normalize_taxonomy_key(label))
    if record is None:
        return None
    return ncbi_record_to_normalized_taxon(record)


class NCBITaxonomyClient:
    """Fetch taxonomy records from NCBI Entrez E-utilities."""

    def __init__(
        self,
        *,
        http_client: HttpClient | None = None,
        request_timeout: float = 30.0,
        tool_name: str | None = None,
        contact_email: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved = settings or get_settings()
        self._http_client = http_client or UrllibHttpClient()
        self.request_timeout = request_timeout
        self.tool_name = tool_name or resolved.ncbi_tool_name
        self.contact_email = contact_email or resolved.ncbi_email

    def search_taxid(self, term: str) -> str | None:
        params = {
            "db": "taxonomy",
            "term": term,
            "retmode": "json",
            "tool": self.tool_name,
        }
        if self.contact_email:
            params["email"] = self.contact_email
        response = self._http_client.get(
            f"{NCBI_EUTILS_BASE}/esearch.fcgi",
            params=params,
            timeout=self.request_timeout,
        )
        if response.status_code >= 400:
            raise NCBITaxonomyError(f"NCBI taxonomy search failed ({response.status_code})")
        payload = response.json()
        idlist = payload.get("esearchresult", {}).get("idlist", [])
        return str(idlist[0]) if idlist else None

    def fetch_records(self, taxids: list[str]) -> list[NCBITaxonomyRecord]:
        if not taxids:
            return []
        params = {
            "db": "taxonomy",
            "id": ",".join(taxids),
            "retmode": "xml",
            "tool": self.tool_name,
        }
        if self.contact_email:
            params["email"] = self.contact_email
        response = self._http_client.get(
            f"{NCBI_EUTILS_BASE}/efetch.fcgi",
            params=params,
            timeout=self.request_timeout,
        )
        if response.status_code >= 400:
            raise NCBITaxonomyError(f"NCBI taxonomy fetch failed ({response.status_code})")
        return parse_taxonomy_xml(response.text)


def fetch_bounded_ncbi_taxonomy_records(
    client: NCBITaxonomyClient,
    queries: tuple[str, ...] = DEFAULT_BOUNDED_TAXONOMY_QUERIES,
) -> dict[str, NCBITaxonomyRecord]:
    taxid_by_query: dict[str, str] = {}
    for query in queries:
        taxid = client.search_taxid(query)
        if taxid:
            taxid_by_query[query] = taxid
    records_by_id = {
        record.taxid: record
        for record in client.fetch_records(list(dict.fromkeys(taxid_by_query.values())))
    }
    bounded: dict[str, NCBITaxonomyRecord] = {}
    for query, taxid in taxid_by_query.items():
        base = records_by_id.get(taxid)
        if base is None:
            continue
        bounded[normalize_taxonomy_key(query)] = NCBITaxonomyRecord(
            taxid=base.taxid,
            scientific_name=base.scientific_name,
            rank=base.rank,
            lineage=base.lineage,
            lineage_ex=list(base.lineage_ex),
            synonyms=list(base.synonyms),
            genus=base.genus,
            species=base.species,
            family=base.family,
            query_label=query,
            provenance=dict(base.provenance),
        )
    return bounded


def cache_payload_from_records(
    records: dict[str, NCBITaxonomyRecord],
    *,
    cache_id: str = "ncbi_bounded_v1",
) -> dict[str, Any]:
    fetched_at = datetime.now(tz=timezone.utc).isoformat()
    return {
        "metadata": {
            "cache_id": cache_id,
            "source_name": "ncbi_taxonomy",
            "entry_count": len(records),
            "real_bounded_ncbi_taxonomy": True,
            "not_synthetic_fixture": True,
            "license": "NCBI public domain",
            "fetched_at_utc": fetched_at,
            "policy_url": NCBI_TAXONOMY_POLICY_URL,
        },
        "entries": {
            key: {
                "query_label": record.query_label or key,
                "taxid": record.taxid,
                "scientific_name": record.scientific_name,
                "rank": record.rank,
                "lineage": record.lineage,
                "lineage_ex": record.lineage_ex,
                "synonyms": record.synonyms,
                "genus": record.genus,
                "species": record.species,
                "family": record.family,
                "provenance": {
                    **dict(record.provenance),
                    "fetched_at_utc": fetched_at,
                },
            }
            for key, record in records.items()
        },
    }


def write_ncbi_taxonomy_cache(
    payload: dict[str, Any],
    output_dir: str | Path,
) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    cache_path = directory / "cache.json"
    cache_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "cache_id": payload.get("metadata", {}).get("cache_id", "unknown"),
        "entry_count": payload.get("metadata", {}).get("entry_count", 0),
        "source_name": "ncbi_taxonomy",
        "files": {
            "cache.json": {
                "entry_count": payload.get("metadata", {}).get("entry_count", 0),
            }
        },
        "license": "NCBI public domain",
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return cache_path


def build_ncbi_search_url(term: str) -> str:
    return f"{NCBI_EUTILS_BASE}/esearch.fcgi?{urlencode({'db': 'taxonomy', 'term': term, 'retmode': 'json'})}"
