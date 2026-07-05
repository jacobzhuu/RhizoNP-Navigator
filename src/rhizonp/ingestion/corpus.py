from __future__ import annotations

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

    metadata = {
        "corpus_name": config.get("corpus_name", "unnamed_corpus"),
        "description": config.get("description"),
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "source_name": adapter.source_name,
        "metadata_only": True,
        "full_text": False,
        "max_total_records": max_total_records,
        "record_count": len(normalized_records),
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


def save_corpus_snapshot(snapshot: Mapping[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return path


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
