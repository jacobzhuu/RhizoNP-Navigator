from __future__ import annotations

import json
import math
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from rhizonp.domain.models import PaperChunk
from rhizonp.literature.embeddings import LiteratureEmbeddingProvider

TextEmbeddingProvider = LiteratureEmbeddingProvider


@dataclass(frozen=True)
class VectorIndexEntry:
    chunk_id: str
    paper_id: str
    text: str
    metadata: dict[str, Any]
    vector: list[float]


@dataclass(frozen=True)
class VectorIndexHit:
    chunk_id: str
    score: float
    metadata: dict[str, Any]


class LiteratureVectorIndex(Protocol):
    index_name: str

    def search(
        self,
        query_vector: Sequence[float],
        *,
        top_k: int,
        candidate_chunk_ids: Collection[str] | None = None,
    ) -> list[VectorIndexHit]:
        ...


class InMemoryLiteratureVectorIndex:
    index_name = "in_memory"
    schema_version = 1

    def __init__(
        self,
        entries: Iterable[VectorIndexEntry],
        *,
        embedding_provider_name: str | None = None,
    ) -> None:
        self.entries = list(entries)
        self.embedding_provider_name = embedding_provider_name
        dimensions = {len(entry.vector) for entry in self.entries}
        if len(dimensions) > 1:
            raise ValueError("All vector index entries must have the same dimensions.")
        self.dimensions = next(iter(dimensions), 0)

    @classmethod
    def from_chunks(
        cls,
        chunks: Iterable[PaperChunk],
        embedding_provider: TextEmbeddingProvider,
    ) -> InMemoryLiteratureVectorIndex:
        entries: list[VectorIndexEntry] = []
        for chunk in chunks:
            paper = chunk.paper
            metadata = {
                **dict(chunk.chunk_metadata),
                "chunk_id": str(chunk.chunk_id),
                "paper_id": str(chunk.paper_id),
                "section": chunk.section,
                "paragraph_index": chunk.paragraph_index,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "source_hash": chunk.source_hash,
                "doi": paper.doi if paper is not None else None,
                "source_url": paper.source_url if paper is not None else None,
                "title": paper.title if paper is not None else None,
                "year": paper.year if paper is not None else None,
                "journal": paper.journal if paper is not None else None,
            }
            entries.append(
                VectorIndexEntry(
                    chunk_id=str(chunk.chunk_id),
                    paper_id=str(chunk.paper_id),
                    text=chunk.text,
                    metadata=metadata,
                    vector=embedding_provider.embed(chunk.text),
                )
            )
        return cls(entries, embedding_provider_name=embedding_provider.provider_name)

    def search(
        self,
        query_vector: Sequence[float],
        *,
        top_k: int,
        candidate_chunk_ids: Collection[str] | None = None,
    ) -> list[VectorIndexHit]:
        if top_k <= 0 or not self.entries:
            return []

        query_values = [float(value) for value in query_vector]
        if len(query_values) != self.dimensions:
            raise ValueError(
                f"Query vector has {len(query_values)} dimensions, "
                f"but index has {self.dimensions}."
            )

        allowed_ids = {str(chunk_id) for chunk_id in candidate_chunk_ids} if candidate_chunk_ids else None
        hits: list[VectorIndexHit] = []
        for entry in self.entries:
            if allowed_ids is not None and entry.chunk_id not in allowed_ids:
                continue
            score = _cosine_similarity(query_values, entry.vector)
            if score <= 0:
                continue
            hits.append(
                VectorIndexHit(
                    chunk_id=entry.chunk_id,
                    score=score,
                    metadata=dict(entry.metadata),
                )
            )
        return sorted(hits, key=lambda hit: (-hit.score, hit.chunk_id))[:top_k]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "index_name": self.index_name,
            "embedding_provider_name": self.embedding_provider_name,
            "dimensions": self.dimensions,
            "entries": [
                {
                    "chunk_id": entry.chunk_id,
                    "paper_id": entry.paper_id,
                    "text": entry.text,
                    "metadata": entry.metadata,
                    "vector": entry.vector,
                }
                for entry in sorted(self.entries, key=lambda item: item.chunk_id)
            ],
        }

    @classmethod
    def from_json_dict(cls, payload: dict[str, Any]) -> InMemoryLiteratureVectorIndex:
        if payload.get("schema_version") != cls.schema_version:
            raise ValueError(f"Unsupported vector index schema_version: {payload.get('schema_version')!r}")
        entries = [
            VectorIndexEntry(
                chunk_id=str(entry["chunk_id"]),
                paper_id=str(entry["paper_id"]),
                text=str(entry["text"]),
                metadata=dict(entry.get("metadata", {})),
                vector=[float(value) for value in entry["vector"]],
            )
            for entry in payload.get("entries", [])
        ]
        index = cls(
            entries,
            embedding_provider_name=payload.get("embedding_provider_name"),
        )
        expected_dimensions = payload.get("dimensions")
        if expected_dimensions is not None and index.dimensions != int(expected_dimensions):
            raise ValueError(
                f"Loaded vector index has {index.dimensions} dimensions, "
                f"but metadata declares {expected_dimensions}."
            )
        return index

    def save(self, path: str | Path) -> None:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.to_json_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> InMemoryLiteratureVectorIndex:
        return cls.from_json_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Vector dimensions do not match.")
    numerator = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)
