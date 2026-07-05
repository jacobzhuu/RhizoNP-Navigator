from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from rhizonp.config import PROJECT_ROOT
from rhizonp.domain.models import Paper, PaperChunk
from rhizonp.literature.adapters import (
    NormalizedLiteratureRecord,
    SyntheticLiteratureAdapter,
    raw_literature_record_from_mapping,
)
from rhizonp.literature.chunking import structured_chunk_record
from rhizonp.storage.repositories import PaperChunkRepository, PaperRepository

DEFAULT_PHASE2_FIXTURE_PATH = PROJECT_ROOT / "data" / "fixtures" / "phase2_literature_demo.json"


@dataclass(frozen=True)
class LiteratureIngestionSummary:
    papers: int
    paper_chunks: int


def ingest_literature_records(
    session: Session,
    records: Iterable[NormalizedLiteratureRecord],
) -> LiteratureIngestionSummary:
    paper_repo = PaperRepository(session)
    chunk_repo = PaperChunkRepository(session)
    paper_count = 0
    chunk_count = 0

    for record in records:
        paper = _find_existing_paper(paper_repo, record)
        if paper is None:
            paper = paper_repo.add(
                Paper(
                    doi=record.doi,
                    pmid=record.pmid,
                    pmcid=record.pmcid,
                    title=record.title,
                    abstract=record.abstract,
                    year=record.year,
                    journal=record.journal,
                    source_url=record.source_url,
                    license=record.license,
                    provenance=dict(record.provenance),
                )
            )
            paper_count += 1

        for chunk in structured_chunk_record(record):
            if chunk_repo.find_by_source_hash(chunk.source_hash) is not None:
                continue
            chunk_repo.add(
                PaperChunk(
                    paper=paper,
                    section=chunk.section,
                    paragraph_index=chunk.paragraph_index,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    text=chunk.text,
                    token_count=chunk.token_count,
                    source_hash=chunk.source_hash,
                    chunk_metadata=chunk.metadata,
                )
            )
            chunk_count += 1

    return LiteratureIngestionSummary(papers=paper_count, paper_chunks=chunk_count)


def load_phase2_literature_fixture(
    session: Session,
    fixture_path: str | Path = DEFAULT_PHASE2_FIXTURE_PATH,
) -> LiteratureIngestionSummary:
    payload = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    raw_records = [
        raw_literature_record_from_mapping(record)
        for record in payload.get("records", [])
    ]
    adapter = SyntheticLiteratureAdapter(raw_records)
    normalized_records = [adapter.normalize(record) for record in adapter.fetch({})]
    return ingest_literature_records(session, normalized_records)


def _find_existing_paper(
    paper_repo: PaperRepository,
    record: NormalizedLiteratureRecord,
) -> Paper | None:
    if record.doi:
        found = paper_repo.find_by_doi(record.doi)
        if found is not None:
            return found
    if record.pmid:
        found = paper_repo.find_by_pmid(record.pmid)
        if found is not None:
            return found
    if record.source_url:
        return paper_repo.find_by_source_url(record.source_url)
    return None
