from __future__ import annotations

import json
from collections.abc import Collection, Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from rhizonp.config import Settings, get_settings
from rhizonp.domain.models import PaperChunk
from rhizonp.literature.embeddings import (
    LiteratureEmbeddingProvider,
    create_literature_embedding_provider,
)
from rhizonp.literature.vector_index import (
    InMemoryLiteratureVectorIndex,
    LiteratureVectorIndex,
    VectorIndexEntry,
    VectorIndexHit,
    _build_vector_index_entries,
)


def faiss_available() -> bool:
    try:
        import faiss  # noqa: F401

        return True
    except ImportError:
        return False


def _require_faiss() -> Any:
    if not faiss_available():
        raise RuntimeError(
            "faiss-cpu is required for FAISS literature vector indexes. "
            "Install project dependencies or use the in_memory backend."
        )
    import faiss

    return faiss


class FaissLiteratureVectorIndex:
    index_name = "faiss"
    schema_version = 1

    def __init__(
        self,
        entries: Iterable[VectorIndexEntry],
        *,
        embedding_provider_name: str | None = None,
    ) -> None:
        faiss = _require_faiss()
        self.entries = list(entries)
        self.embedding_provider_name = embedding_provider_name
        dimensions = {len(entry.vector) for entry in self.entries}
        if len(dimensions) > 1:
            raise ValueError("All vector index entries must have the same dimensions.")
        self.dimensions = next(iter(dimensions), 0)

        if self.dimensions == 0:
            self._faiss_index = None
            return

        vectors = np.array([entry.vector for entry in self.entries], dtype=np.float32)
        faiss.normalize_L2(vectors)
        index = faiss.IndexFlatIP(self.dimensions)
        index.add(vectors)
        self._faiss_index = index

    @classmethod
    def from_chunks(
        cls,
        chunks: Iterable[PaperChunk],
        embedding_provider: LiteratureEmbeddingProvider,
    ) -> FaissLiteratureVectorIndex:
        entries = _build_vector_index_entries(chunks, embedding_provider)
        return cls(entries, embedding_provider_name=embedding_provider.provider_name)

    def search(
        self,
        query_vector: Sequence[float],
        *,
        top_k: int,
        candidate_chunk_ids: Collection[str] | None = None,
    ) -> list[VectorIndexHit]:
        if top_k <= 0 or not self.entries or self._faiss_index is None:
            return []

        faiss = _require_faiss()
        query_values = [float(value) for value in query_vector]
        if len(query_values) != self.dimensions:
            raise ValueError(
                f"Query vector has {len(query_values)} dimensions, "
                f"but index has {self.dimensions}."
            )

        query = np.array([query_values], dtype=np.float32)
        faiss.normalize_L2(query)

        allowed_ids = {str(chunk_id) for chunk_id in candidate_chunk_ids} if candidate_chunk_ids else None
        search_k = top_k
        if allowed_ids is not None:
            search_k = min(len(self.entries), max(top_k * 5, top_k))

        scores, indices = self._faiss_index.search(query, search_k)
        hits: list[VectorIndexHit] = []
        for score, index in zip(scores[0], indices[0], strict=True):
            if index < 0:
                continue
            entry = self.entries[index]
            if allowed_ids is not None and entry.chunk_id not in allowed_ids:
                continue
            if score <= 0:
                continue
            hits.append(
                VectorIndexHit(
                    chunk_id=entry.chunk_id,
                    score=float(score),
                    metadata=dict(entry.metadata),
                )
            )
            if len(hits) >= top_k:
                break
        return sorted(hits, key=lambda hit: (-hit.score, hit.chunk_id))

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

    def save(self, path: str | Path) -> None:
        faiss = _require_faiss()
        output_path = Path(path)
        if output_path.suffix:
            raise ValueError("FAISS literature indexes must be saved to a directory path.")
        output_path.mkdir(parents=True, exist_ok=True)
        if self._faiss_index is not None:
            faiss.write_index(self._faiss_index, str(output_path / "index.faiss"))
        (output_path / "metadata.json").write_text(
            json.dumps(self.to_json_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> FaissLiteratureVectorIndex:
        faiss = _require_faiss()
        input_path = Path(path)
        payload = json.loads((input_path / "metadata.json").read_text(encoding="utf-8"))
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
        index = cls(entries, embedding_provider_name=payload.get("embedding_provider_name"))
        expected_dimensions = payload.get("dimensions")
        if expected_dimensions is not None and index.dimensions != int(expected_dimensions):
            raise ValueError(
                f"Loaded vector index has {index.dimensions} dimensions, "
                f"but metadata declares {expected_dimensions}."
            )

        faiss_path = input_path / "index.faiss"
        if faiss_path.exists() and index.dimensions > 0:
            loaded_faiss = faiss.read_index(str(faiss_path))
            if loaded_faiss.ntotal != len(index.entries):
                raise ValueError(
                    "FAISS index vector count does not match metadata entry count."
                )
            index._faiss_index = loaded_faiss
        return index


def create_literature_vector_index(
    backend: str | None = None,
    *,
    settings: Settings | None = None,
    chunks: Iterable[PaperChunk] | None = None,
    embedding_provider: LiteratureEmbeddingProvider | None = None,
) -> LiteratureVectorIndex:
    if chunks is None:
        raise ValueError("chunks are required to build a literature vector index.")

    resolved_settings = settings or get_settings()
    resolved_backend = (backend or resolved_settings.literature_vector_index_backend).casefold()
    provider = embedding_provider or create_literature_embedding_provider(settings=resolved_settings)

    if resolved_backend == "in_memory":
        return InMemoryLiteratureVectorIndex.from_chunks(chunks, provider)
    if resolved_backend == "faiss":
        return FaissLiteratureVectorIndex.from_chunks(chunks, provider)

    raise ValueError(
        "Unsupported literature_vector_index_backend "
        f"{resolved_backend!r}. Expected 'in_memory' or 'faiss'."
    )
