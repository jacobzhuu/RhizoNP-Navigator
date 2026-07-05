from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class RawLiteratureRecord:
    source_id: str
    title: str
    abstract: str | None = None
    sections: Mapping[str, str] = field(default_factory=dict)
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    year: int | None = None
    journal: str | None = None
    source_url: str | None = None
    license: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedLiteratureRecord:
    source_id: str
    source_name: str
    title: str
    abstract: str | None = None
    sections: Mapping[str, str] = field(default_factory=dict)
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    year: int | None = None
    journal: str | None = None
    source_url: str | None = None
    license: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)


class SourceAdapter(Protocol):
    source_name: str

    def fetch(self, query: Mapping[str, Any]) -> list[RawLiteratureRecord]:
        ...

    def normalize(self, record: RawLiteratureRecord) -> NormalizedLiteratureRecord:
        ...

    def provenance(self, record: RawLiteratureRecord) -> dict[str, Any]:
        ...


class SyntheticLiteratureAdapter:
    source_name = "synthetic_fixture"

    def __init__(self, records: Sequence[RawLiteratureRecord]) -> None:
        self._records = list(records)

    def fetch(self, query: Mapping[str, Any]) -> list[RawLiteratureRecord]:
        query_text = str(query.get("query", "")).strip().casefold()
        if not query_text:
            return list(self._records)
        query_terms = {term for term in query_text.split() if term}
        if not query_terms:
            return list(self._records)

        matched_records: list[RawLiteratureRecord] = []
        for record in self._records:
            haystack = " ".join(
                [
                    record.title,
                    record.abstract or "",
                    *record.sections.values(),
                ]
            ).casefold()
            if all(term in haystack for term in query_terms):
                matched_records.append(record)
        return matched_records

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
        return {
            "source_name": self.source_name,
            "source_id": record.source_id,
            "fixture": True,
            "not_real_literature": True,
        }


def raw_literature_record_from_mapping(payload: Mapping[str, Any]) -> RawLiteratureRecord:
    return RawLiteratureRecord(
        source_id=str(payload["source_id"]),
        title=str(payload["title"]),
        abstract=payload.get("abstract"),
        sections=dict(payload.get("sections", {})),
        doi=payload.get("doi"),
        pmid=payload.get("pmid"),
        pmcid=payload.get("pmcid"),
        year=payload.get("year"),
        journal=payload.get("journal"),
        source_url=payload.get("source_url"),
        license=payload.get("license"),
        metadata=dict(payload.get("metadata", {})),
    )
