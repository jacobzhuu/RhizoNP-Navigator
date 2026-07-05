from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from rhizonp.literature.adapters import NormalizedLiteratureRecord

SECTION_ORDER = (
    "title",
    "abstract",
    "introduction",
    "methods",
    "results",
    "discussion",
    "figure_captions",
    "tables",
)


@dataclass(frozen=True)
class StructuredChunk:
    section: str
    paragraph_index: int
    char_start: int
    char_end: int
    text: str
    token_count: int
    source_hash: str
    metadata: dict[str, Any]


def _iter_ordered_sections(record: NormalizedLiteratureRecord) -> Iterable[tuple[str, str]]:
    available: dict[str, str] = {"title": record.title}
    if record.abstract:
        available["abstract"] = record.abstract
    for section, text in record.sections.items():
        if text:
            available[section.casefold()] = text

    yielded: set[str] = set()
    for section in SECTION_ORDER:
        section_text = available.get(section)
        if section_text:
            yielded.add(section)
            yield section, section_text
    for section, text in available.items():
        if section not in yielded and text:
            yield section, text


def _paragraph_spans(text: str) -> Iterable[tuple[int, int, str]]:
    for match in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", text, flags=re.DOTALL):
        paragraph = re.sub(r"\s+", " ", match.group(0)).strip()
        if paragraph:
            yield match.start(), match.end(), paragraph


def _split_long_text(text: str, *, max_chars: int) -> Iterable[tuple[int, int, str]]:
    if len(text) <= max_chars:
        yield 0, len(text), text
        return

    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            whitespace = text.rfind(" ", start, end)
            if whitespace > start:
                end = whitespace
        window = text[start:end]
        chunk_text = window.strip()
        if chunk_text:
            leading = len(window) - len(window.lstrip())
            yield start + leading, start + leading + len(chunk_text), chunk_text
        start = max(end, start + 1)


def _source_hash(
    record: NormalizedLiteratureRecord,
    *,
    section: str,
    char_start: int,
    char_end: int,
    text: str,
) -> str:
    source_key = record.doi or record.source_url or record.source_id or record.title
    digest = hashlib.sha256()
    digest.update(f"{source_key}|{section}|{char_start}|{char_end}|{text}".encode())
    return digest.hexdigest()


def structured_chunk_record(
    record: NormalizedLiteratureRecord,
    *,
    max_chars: int = 1200,
) -> list[StructuredChunk]:
    chunks: list[StructuredChunk] = []
    global_offset = 0
    paragraph_index = 0

    for section, section_text in _iter_ordered_sections(record):
        section_offset = global_offset
        for paragraph_start, _paragraph_end, paragraph in _paragraph_spans(section_text):
            for local_start, local_end, chunk_text in _split_long_text(
                paragraph,
                max_chars=max_chars,
            ):
                char_start = section_offset + paragraph_start + local_start
                char_end = section_offset + paragraph_start + local_end
                metadata = {
                    "source_type": "paper",
                    "source_name": record.source_name,
                    "source_id": record.source_id,
                    "doi": record.doi,
                    "section": section,
                    "taxa": list(record.metadata.get("taxa", [])),
                    "compounds": list(record.metadata.get("compounds", [])),
                    "host": list(record.metadata.get("host", [])),
                    "fixture": bool(record.provenance.get("fixture", False)),
                }
                chunks.append(
                    StructuredChunk(
                        section=section,
                        paragraph_index=paragraph_index,
                        char_start=char_start,
                        char_end=char_end,
                        text=chunk_text,
                        token_count=len(re.findall(r"\w+", chunk_text)),
                        source_hash=_source_hash(
                            record,
                            section=section,
                            char_start=char_start,
                            char_end=char_end,
                            text=chunk_text,
                        ),
                        metadata=metadata,
                    )
                )
                paragraph_index += 1
        global_offset += len(section_text) + 2

    return chunks
