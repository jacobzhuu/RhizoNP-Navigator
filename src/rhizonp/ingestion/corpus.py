from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rhizonp.config import PROJECT_ROOT
from rhizonp.literature.adapters import NormalizedLiteratureRecord, RawLiteratureRecord
from rhizonp.literature.pubmed_adapter import PubMedEutilitiesAdapter

DEFAULT_DOMAIN_CORPUS_QUERIES = (
    PROJECT_ROOT / "data" / "eval" / "domain_corpus_queries.json"
)
DEFAULT_CORPUS_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "pubmed_corpus"
DEFAULT_CORPUS_SNAPSHOTS_DIR = PROJECT_ROOT / "data" / "snapshots" / "pubmed"

DEDUPLICATION_RULES = {
    "key": "pmid",
    "fallback_key": "source_id",
    "strategy": "first_seen_wins",
    "description": "Records deduplicated by PMID (or source_id when PMID absent); first query run wins.",
}


@dataclass(frozen=True)
class CorpusQuerySpec:
    query_id: str
    term: str
    retmax: int


@dataclass(frozen=True)
class CorpusFetchSummary:
    corpus_name: str
    query_count: int
    record_count: int
    output_path: Path


def load_corpus_query_config(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if "queries" not in payload:
        raise ValueError("Corpus query config must include a 'queries' list.")
    return payload


def parse_corpus_queries(config: Mapping[str, Any]) -> list[CorpusQuerySpec]:
    default_retmax = int(config.get("default_retmax", 5))
    queries: list[CorpusQuerySpec] = []
    for entry in config.get("queries", []):
        queries.append(
            CorpusQuerySpec(
                query_id=str(entry["query_id"]),
                term=str(entry["term"]),
                retmax=int(entry.get("retmax", default_retmax)),
            )
        )
    return queries


def fetch_domain_corpus(
    adapter: PubMedEutilitiesAdapter,
    config: Mapping[str, Any],
) -> tuple[list[NormalizedLiteratureRecord], dict[str, Any]]:
    max_total_records = int(config.get("max_total_records", 50))
    seen_pmids: set[str] = set()
    normalized_records: list[NormalizedLiteratureRecord] = []
    query_runs: list[dict[str, Any]] = []

    for query_spec in parse_corpus_queries(config):
        if len(normalized_records) >= max_total_records:
            break
        remaining = max_total_records - len(normalized_records)
        retmax = min(query_spec.retmax, remaining)
        raw_records = adapter.fetch(
            {
                "query": query_spec.term,
                "retmax": retmax,
                "query_id": query_spec.query_id,
            }
        )
        added = 0
        for raw_record in raw_records:
            pmid = raw_record.pmid or raw_record.source_id
            if pmid in seen_pmids:
                continue
            seen_pmids.add(pmid)
            normalized_records.append(adapter.normalize(raw_record))
            added += 1
            if len(normalized_records) >= max_total_records:
                break
        query_runs.append(
            {
                "query_id": query_spec.query_id,
                "term": query_spec.term,
                "retmax": retmax,
                "records_added": added,
                "pmids": [record.pmid for record in normalized_records[-added:]],
            }
        )

    query_config_path = config.get("query_config_path")
    metadata = {
        "corpus_id": config.get("corpus_id") or config.get("corpus_name", "unnamed_corpus"),
        "corpus_name": config.get("corpus_name", "unnamed_corpus"),
        "description": config.get("description"),
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "source_name": adapter.source_name,
        "metadata_only": True,
        "full_text": False,
        "max_total_records": max_total_records,
        "record_count": len(normalized_records),
        "deduplication_rules": dict(DEDUPLICATION_RULES),
        "query_config_path": str(query_config_path) if query_config_path else None,
        "query_runs": query_runs,
    }
    return normalized_records, metadata


def corpus_snapshot_from_records(
    records: Iterable[NormalizedLiteratureRecord],
    *,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "metadata": dict(metadata),
        "records": [
            {
                "source_id": record.source_id,
                "source_name": record.source_name,
                "title": record.title,
                "abstract": record.abstract,
                "sections": dict(record.sections),
                "doi": record.doi,
                "pmid": record.pmid,
                "pmcid": record.pmcid,
                "year": record.year,
                "journal": record.journal,
                "source_url": record.source_url,
                "license": record.license,
                "metadata": dict(record.metadata),
                "provenance": dict(record.provenance),
            }
            for record in records
        ],
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_corpus_manifest(
    snapshot: Mapping[str, Any],
    *,
    corpus_file: str,
    corpus_checksum: str,
    query_config_path: str | Path | None = None,
    query_config_checksum: str | None = None,
) -> dict[str, Any]:
    metadata = dict(snapshot.get("metadata", {}))
    manifest: dict[str, Any] = {
        "corpus_id": metadata.get("corpus_id") or metadata.get("corpus_name"),
        "corpus_name": metadata.get("corpus_name"),
        "created_at": metadata.get("fetched_at"),
        "paper_count": metadata.get("record_count", len(snapshot.get("records", []))),
        "metadata_only": metadata.get("metadata_only", True),
        "full_text": metadata.get("full_text", False),
        "deduplication_rules": metadata.get("deduplication_rules", DEDUPLICATION_RULES),
        "query_config": {
            "path": str(query_config_path) if query_config_path else metadata.get("query_config_path"),
            "checksum_sha256": query_config_checksum,
        },
        "files": {
            corpus_file: {
                "checksum_sha256": corpus_checksum,
                "record_count": metadata.get("record_count", len(snapshot.get("records", []))),
            }
        },
        "source_name": metadata.get("source_name"),
        "description": metadata.get("description"),
    }
    return manifest


def save_corpus_snapshot(snapshot: Mapping[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return path


def save_versioned_corpus_snapshot(
    snapshot: Mapping[str, Any],
    output_dir: str | Path,
    *,
    query_config_path: str | Path | None = None,
    corpus_filename: str = "corpus.json",
    manifest_filename: str = "manifest.json",
) -> tuple[Path, Path, Path]:
    """Persist an immutable versioned corpus directory with manifest and checksums."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    corpus_path = directory / corpus_filename
    corpus_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    corpus_checksum = sha256_file(corpus_path)

    query_checksum: str | None = None
    if query_config_path is not None:
        query_path = Path(query_config_path)
        if query_path.is_file():
            query_checksum = sha256_file(query_path)

    manifest = build_corpus_manifest(
        snapshot,
        corpus_file=corpus_filename,
        corpus_checksum=corpus_checksum,
        query_config_path=query_config_path,
        query_config_checksum=query_checksum,
    )
    manifest_path = directory / manifest_filename
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    pmid_list_path = save_pmid_list(snapshot, directory / "pmids.json")
    return corpus_path, manifest_path, pmid_list_path


def build_pmid_list(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    metadata = dict(snapshot.get("metadata", {}))
    pmids = [str(entry.get("pmid") or entry.get("source_id")) for entry in snapshot.get("records", [])]
    return {
        "corpus_id": metadata.get("corpus_id") or metadata.get("corpus_name"),
        "corpus_name": metadata.get("corpus_name"),
        "record_count": len(pmids),
        "metadata_only": metadata.get("metadata_only", True),
        "full_text": metadata.get("full_text", False),
        "pmids": pmids,
    }


def save_pmid_list(snapshot: Mapping[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_pmid_list(snapshot), indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_corpus_manifest(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_corpus_snapshot_directory(snapshot_dir: str | Path) -> dict[str, Any]:
    """Verify corpus file checksum against manifest; returns manifest on success."""
    directory = Path(snapshot_dir)
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing manifest.json in {directory}")

    manifest = load_corpus_manifest(manifest_path)
    files = manifest.get("files", {})
    for filename, file_meta in files.items():
        corpus_path = directory / filename
        if not corpus_path.is_file():
            raise FileNotFoundError(f"Missing corpus file {filename} in {directory}")
        expected = file_meta.get("checksum_sha256")
        actual = sha256_file(corpus_path)
        if expected and actual != expected:
            raise ValueError(
                f"Checksum mismatch for {filename}: expected {expected}, got {actual}"
            )
    return manifest


def load_corpus_snapshot(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalized_records_from_snapshot(snapshot: Mapping[str, Any]) -> list[NormalizedLiteratureRecord]:
    records: list[NormalizedLiteratureRecord] = []
    for entry in snapshot.get("records", []):
        records.append(
            NormalizedLiteratureRecord(
                source_id=str(entry["source_id"]),
                source_name=str(entry.get("source_name", "unknown")),
                title=str(entry["title"]),
                abstract=entry.get("abstract"),
                sections=dict(entry.get("sections", {})),
                doi=entry.get("doi"),
                pmid=entry.get("pmid"),
                pmcid=entry.get("pmcid"),
                year=entry.get("year"),
                journal=entry.get("journal"),
                source_url=entry.get("source_url"),
                license=entry.get("license"),
                metadata=dict(entry.get("metadata", {})),
                provenance=dict(entry.get("provenance", {})),
            )
        )
    return records


def raw_records_from_snapshot(snapshot: Mapping[str, Any]) -> list[RawLiteratureRecord]:
    return [
        RawLiteratureRecord(
            source_id=str(entry["source_id"]),
            title=str(entry["title"]),
            abstract=entry.get("abstract"),
            sections=dict(entry.get("sections", {})),
            doi=entry.get("doi"),
            pmid=entry.get("pmid"),
            pmcid=entry.get("pmcid"),
            year=entry.get("year"),
            journal=entry.get("journal"),
            source_url=entry.get("source_url"),
            license=entry.get("license"),
            metadata=dict(entry.get("metadata", {})),
        )
        for entry in snapshot.get("records", [])
    ]
