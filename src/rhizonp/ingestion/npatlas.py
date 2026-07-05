from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from rhizonp.config import PROJECT_ROOT
from rhizonp.literature.http_client import HttpClient, UrllibHttpClient

NPATLAS_API_BASE = "https://www.npatlas.org/api/v1"
NPATLAS_LICENSE = "CC-BY-NC-4.0"
DEFAULT_NPATLAS_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "snapshots" / "npatlas" / "rhizonp_domain_v1"
DEFAULT_NPATLAS_SNAPSHOT_PATH = DEFAULT_NPATLAS_SNAPSHOT_DIR / "snapshot.json"
DEFAULT_BOUNDED_TAXA: tuple[tuple[str, str, int], ...] = (
    ("Streptomyces", "genus", 8),
    ("Bacillus", "genus", 4),
)


class NPAtlasAdapterError(RuntimeError):
    """Base error for NPAtlas adapter failures."""


@dataclass(frozen=True)
class RawNPAtlasRecord:
    npaid: str
    compound_name: str
    producer_taxon: str
    producer_genus: str | None = None
    producer_species: str | None = None
    inchikey: str | None = None
    smiles: str | None = None
    mol_formula: str | None = None
    origin_reference: Mapping[str, Any] = field(default_factory=dict)
    origin_organism: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedNPAtlasRecord:
    npaid: str
    compound_name: str
    producer_taxon: str
    source_database: str
    external_record_id: str
    inchikey: str | None = None
    smiles: str | None = None
    mol_formula: str | None = None
    origin_reference: dict[str, Any] = field(default_factory=dict)
    origin_organism: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)


class NPAtlasSourceAdapter(Protocol):
    source_name: str

    def fetch(self, query: Mapping[str, Any]) -> list[RawNPAtlasRecord]:
        ...

    def normalize(self, record: RawNPAtlasRecord) -> NormalizedNPAtlasRecord:
        ...

    def provenance(self, record: RawNPAtlasRecord) -> dict[str, Any]:
        ...


def _canonical_producer_taxon(
    *,
    producer_taxon: str,
    producer_genus: str | None,
    producer_species: str | None,
) -> str:
    taxon = producer_taxon.strip()
    genus = (producer_genus or "").strip()
    species = (producer_species or "").strip()
    if genus and species and not taxon.lower().startswith(genus.lower()):
        return f"{genus} {species}".strip()
    if genus and not taxon:
        return genus
    return taxon


def normalize_npatlas_record(record: RawNPAtlasRecord) -> NormalizedNPAtlasRecord:
    producer = _canonical_producer_taxon(
        producer_taxon=record.producer_taxon,
        producer_genus=record.producer_genus,
        producer_species=record.producer_species,
    )
    provenance = {
        "source": "npatlas",
        "npaid": record.npaid,
        "license": NPATLAS_LICENSE,
        "source_url": f"https://www.npatlas.org/explore/compounds/{record.npaid}",
        "real_bounded_npatlas": True,
        "not_synthetic_fixture": True,
        "origin_reference": dict(record.origin_reference),
        "origin_organism": dict(record.origin_organism),
    }
    return NormalizedNPAtlasRecord(
        npaid=record.npaid,
        compound_name=record.compound_name,
        producer_taxon=producer,
        source_database="npatlas",
        external_record_id=record.npaid,
        inchikey=record.inchikey,
        smiles=record.smiles,
        mol_formula=record.mol_formula,
        origin_reference=dict(record.origin_reference),
        origin_organism=dict(record.origin_organism),
        provenance=provenance,
    )


class NPAtlasHttpAdapter:
    """Read-only NPAtlas REST adapter (rate-limited public API)."""

    source_name = "npatlas_api"

    def __init__(
        self,
        *,
        http_client: HttpClient | None = None,
        request_timeout: float = 30.0,
        api_base: str = NPATLAS_API_BASE,
    ) -> None:
        self._http_client = http_client or UrllibHttpClient()
        self.request_timeout = request_timeout
        self.api_base = api_base.rstrip("/")

    def fetch(self, query: Mapping[str, Any]) -> list[RawNPAtlasRecord]:
        taxon = str(query.get("taxon") or "").strip()
        if not taxon:
            return []
        rank = str(query.get("rank") or "all")
        limit = min(int(query.get("limit", 10)), 100)
        skip = max(int(query.get("skip", 0)), 0)
        params = {"taxon": taxon, "rank": rank, "limit": str(limit), "skip": str(skip)}
        response = self._http_client.post(
            f"{self.api_base}/compounds/taxonSearch",
            params=params,
            timeout=self.request_timeout,
        )
        if response.status_code >= 400:
            raise NPAtlasAdapterError(
                f"NPAtlas taxonSearch failed ({response.status_code}): {response.text[:200]}"
            )
        compounds = response.json()
        if not isinstance(compounds, list):
            raise NPAtlasAdapterError("NPAtlas taxonSearch returned unexpected payload.")

        records: list[RawNPAtlasRecord] = []
        for compound in compounds:
            npaid = str(compound.get("npaid") or "").strip()
            if not npaid:
                continue
            full = self._fetch_compound(npaid)
            records.append(self._raw_from_api_payload(full))
        return records

    def normalize(self, record: RawNPAtlasRecord) -> NormalizedNPAtlasRecord:
        return normalize_npatlas_record(record)

    def provenance(self, record: RawNPAtlasRecord) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "api_base": self.api_base,
            "npaid": record.npaid,
            "license": NPATLAS_LICENSE,
            "source_url": f"https://www.npatlas.org/explore/compounds/{record.npaid}",
        }

    def _fetch_compound(self, npaid: str) -> dict[str, Any]:
        response = self._http_client.get(
            f"{self.api_base}/compound/{npaid}",
            timeout=self.request_timeout,
        )
        if response.status_code >= 400:
            raise NPAtlasAdapterError(
                f"NPAtlas compound fetch failed for {npaid} ({response.status_code})"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise NPAtlasAdapterError(f"NPAtlas compound payload for {npaid} is not an object.")
        return payload

    def _raw_from_api_payload(self, payload: Mapping[str, Any]) -> RawNPAtlasRecord:
        org = payload.get("origin_organism") or {}
        tax = org.get("taxon") or {}
        species = str(org.get("species") or "").strip() or None
        genus = str(org.get("genus") or tax.get("name") or "").strip() or None
        producer = species or genus or "unknown"
        ref = payload.get("origin_reference") or {}
        return RawNPAtlasRecord(
            npaid=str(payload["npaid"]),
            compound_name=str(payload.get("original_name") or payload.get("npaid")),
            producer_taxon=producer,
            producer_genus=genus,
            producer_species=species,
            inchikey=payload.get("inchikey"),
            smiles=payload.get("smiles"),
            mol_formula=payload.get("mol_formula"),
            origin_reference={
                "doi": ref.get("doi"),
                "pmid": ref.get("pmid"),
                "title": ref.get("title"),
                "journal": ref.get("journal"),
                "year": ref.get("year"),
            },
            origin_organism={
                "genus": genus,
                "species": species,
                "ncbi_id": tax.get("ncbi_id"),
                "taxon_rank": tax.get("rank"),
            },
        )


def fetch_bounded_npatlas_records(
    adapter: NPAtlasHttpAdapter,
    taxa: Sequence[tuple[str, str, int]] = DEFAULT_BOUNDED_TAXA,
) -> list[NormalizedNPAtlasRecord]:
    seen: set[str] = set()
    normalized: list[NormalizedNPAtlasRecord] = []
    for taxon, rank, limit in taxa:
        raw_records = adapter.fetch({"taxon": taxon, "rank": rank, "limit": limit})
        for raw in raw_records:
            if raw.npaid in seen:
                continue
            seen.add(raw.npaid)
            normalized.append(adapter.normalize(raw))
    return normalized


def snapshot_from_records(
    records: Sequence[NormalizedNPAtlasRecord],
    *,
    snapshot_id: str = "rhizonp_domain_v1",
    description: str = "Bounded NPAtlas snapshot for RhizoNP Navigator.",
) -> dict[str, Any]:
    fetched_at = datetime.now(tz=timezone.utc).isoformat()
    return {
        "metadata": {
            "snapshot_id": snapshot_id,
            "source_name": "npatlas_api",
            "description": description,
            "record_count": len(records),
            "license": NPATLAS_LICENSE,
            "real_bounded_npatlas": True,
            "not_synthetic_fixture": True,
            "fetched_at_utc": fetched_at,
        },
        "records": [
            {
                "npaid": record.npaid,
                "compound_name": record.compound_name,
                "producer_taxon": record.producer_taxon,
                "producer_genus": record.origin_organism.get("genus"),
                "producer_species": record.origin_organism.get("species"),
                "source_database": record.source_database,
                "external_record_id": record.external_record_id,
                "inchikey": record.inchikey,
                "smiles": record.smiles,
                "mol_formula": record.mol_formula,
                "origin_reference": dict(record.origin_reference),
                "origin_organism": dict(record.origin_organism),
                "provenance": {
                    **dict(record.provenance),
                    "fetched_at_utc": fetched_at,
                },
            }
            for record in records
        ],
    }


def write_npatlas_snapshot(
    snapshot: Mapping[str, Any],
    output_dir: str | Path,
) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    snapshot_path = directory / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "snapshot_id": snapshot.get("metadata", {}).get("snapshot_id", "unknown"),
        "source_name": snapshot.get("metadata", {}).get("source_name", "npatlas_api"),
        "record_count": snapshot.get("metadata", {}).get("record_count", 0),
        "license": NPATLAS_LICENSE,
        "files": {
            "snapshot.json": {
                "record_count": snapshot.get("metadata", {}).get("record_count", 0),
            }
        },
        "public_repository_policy": "commit_bounded_metadata_snapshot",
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return snapshot_path


def load_bounded_npatlas_snapshot(
    snapshot_path: str | Path = DEFAULT_NPATLAS_SNAPSHOT_PATH,
) -> list[NormalizedNPAtlasRecord]:
    path = Path(snapshot_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata = payload.get("metadata") or {}
    if not metadata.get("real_bounded_npatlas"):
        raise ValueError(f"NPAtlas snapshot at {path} is not marked as a real bounded snapshot.")

    records: list[NormalizedNPAtlasRecord] = []
    for item in payload.get("records", []):
        raw = RawNPAtlasRecord(
            npaid=str(item["npaid"]),
            compound_name=str(item["compound_name"]),
            producer_taxon=str(item["producer_taxon"]),
            producer_genus=item.get("producer_genus"),
            producer_species=item.get("producer_species"),
            inchikey=item.get("inchikey"),
            smiles=item.get("smiles"),
            mol_formula=item.get("mol_formula"),
            origin_reference=dict(item.get("origin_reference") or {}),
            origin_organism=dict(item.get("origin_organism") or {}),
            metadata={"snapshot_path": str(path)},
        )
        records.append(normalize_npatlas_record(raw))
    return records
