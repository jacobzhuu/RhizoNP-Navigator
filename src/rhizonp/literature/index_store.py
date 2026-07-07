from __future__ import annotations

import hashlib
import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

if sys.platform == "win32":
    import msvcrt

    def _lock_file_exclusive(lock_file: TextIO) -> None:
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock_file(lock_file: TextIO) -> None:
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock_file_exclusive(lock_file: TextIO) -> None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

    def _unlock_file(lock_file: TextIO) -> None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

from sqlalchemy import select
from sqlalchemy.orm import Session

from rhizonp import __version__ as package_version
from rhizonp.domain.models import PaperChunk
from rhizonp.literature.corpus_state import (
    CHUNK_SCHEMA_VERSION,
    compute_chunk_checksums,
    get_corpus_revision,
    get_corpus_state,
)
from rhizonp.literature.embeddings import LiteratureEmbeddingProvider
from rhizonp.literature.faiss_index import FaissLiteratureVectorIndex
from rhizonp.literature.retrieval_settings import ResolvedLiteratureRetrievalSettings

MANIFEST_SCHEMA_VERSION = 1
CURRENT_FILENAME = "CURRENT"
LOCK_FILENAME = ".build.lock"
BUILDS_DIRNAME = "builds"


class IndexStaleError(RuntimeError):
    """Raised when the on-disk FAISS build does not match the active corpus revision."""


class IndexNotFoundError(RuntimeError):
    """Raised when no active FAISS build is available."""


@dataclass(frozen=True)
class IndexBuildSummary:
    build_id: str
    build_dir: Path
    corpus_revision: int
    chunk_count: int
    skipped: bool


def index_root(settings: ResolvedLiteratureRetrievalSettings) -> Path:
    return settings.faiss_index_path


def _builds_dir(index_root_path: Path) -> Path:
    return index_root_path / BUILDS_DIRNAME


def _lock_path(index_root_path: Path) -> Path:
    return index_root_path / LOCK_FILENAME


def read_current_build_id(index_root_path: Path) -> str | None:
    current_path = index_root_path / CURRENT_FILENAME
    if not current_path.is_file():
        return None
    build_id = current_path.read_text(encoding="utf-8").strip()
    return build_id or None


def resolve_active_build_dir(index_root_path: Path) -> Path:
    build_id = read_current_build_id(index_root_path)
    if not build_id:
        raise IndexNotFoundError(f"No CURRENT pointer found under {index_root_path}")
    build_dir = _builds_dir(index_root_path) / build_id
    if not build_dir.is_dir():
        raise IndexNotFoundError(f"Active build directory does not exist: {build_dir}")
    return build_dir


def load_build_manifest(build_dir: Path) -> dict[str, Any]:
    manifest_path = build_dir / "manifest.json"
    if not manifest_path.is_file():
        raise IndexNotFoundError(f"manifest.json missing in {build_dir}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _manifest_corpus_revision(manifest: dict[str, Any]) -> int:
    corpus = manifest.get("corpus") or {}
    return int(corpus.get("revision", -1))


def is_index_stale(
    session: Session,
    index_root_path: Path,
    *,
    settings: ResolvedLiteratureRetrievalSettings,
) -> bool:
    build_id = read_current_build_id(index_root_path)
    if not build_id:
        return True
    try:
        build_dir = resolve_active_build_dir(index_root_path)
        manifest = load_build_manifest(build_dir)
    except IndexNotFoundError:
        return True
    db_revision = get_corpus_revision(session)
    if _manifest_corpus_revision(manifest) != db_revision:
        return True
    return not validate_manifest_against_settings(manifest, settings)


def validate_manifest_against_settings(
    manifest: dict[str, Any],
    settings: ResolvedLiteratureRetrievalSettings,
) -> bool:
    if int(manifest.get("schema_version", -1)) != MANIFEST_SCHEMA_VERSION:
        return False
    embedding = manifest.get("embedding") or {}
    faiss_meta = manifest.get("faiss") or {}
    if embedding.get("provider") != settings.embedding_provider:
        return False
    if embedding.get("model_id") != settings.embedding_model:
        return False
    if faiss_meta.get("index_type") != "IndexFlatIP":
        return False
    if faiss_meta.get("metric") != "inner_product":
        return False
    if embedding.get("normalize_embeddings") is not True:
        return False
    return True


def build_manifest_payload(
    *,
    build_id: str,
    corpus_revision: int,
    chunk_count: int,
    content_checksum: str,
    ordered_chunk_ids_checksum: str,
    settings: ResolvedLiteratureRetrievalSettings,
    embedding_dimension: int,
    model_revision: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "build_id": build_id,
        "corpus": {
            "revision": corpus_revision,
            "chunk_count": chunk_count,
            "content_checksum": content_checksum,
            "ordered_chunk_ids_checksum": ordered_chunk_ids_checksum,
            "chunk_schema_version": CHUNK_SCHEMA_VERSION,
        },
        "embedding": {
            "provider": settings.embedding_provider,
            "model_id": settings.embedding_model,
            "model_revision": model_revision,
            "dimension": embedding_dimension,
            "normalize_embeddings": True,
        },
        "faiss": {
            "index_type": "IndexFlatIP",
            "metric": "inner_product",
        },
        "build": {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "package_version": package_version,
        },
    }


def _build_id_for_revision(corpus_revision: int, content_checksum: str) -> str:
    digest = hashlib.sha256(f"{corpus_revision}:{content_checksum}".encode()).hexdigest()[:12]
    return f"rev_{corpus_revision}_{digest}"


@contextmanager
def index_build_lock(index_root_path: Path):
    index_root_path.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(index_root_path)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        _lock_file_exclusive(lock_file)
        try:
            yield
        finally:
            _unlock_file(lock_file)


def _write_id_map(build_dir: Path, chunk_ids: list[str]) -> None:
    payload = {"chunk_ids": chunk_ids}
    (build_dir / "id_map.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _atomic_replace_current(index_root_path: Path, build_id: str) -> None:
    current_path = index_root_path / CURRENT_FILENAME
    tmp_path = index_root_path / f"{CURRENT_FILENAME}.tmp"
    tmp_path.write_text(build_id, encoding="utf-8")
    os.replace(tmp_path, current_path)


def _prune_old_builds(index_root_path: Path, *, keep: int = 2) -> None:
    builds_dir = _builds_dir(index_root_path)
    if not builds_dir.is_dir():
        return
    build_dirs = sorted(
        (path for path in builds_dir.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    active_id = read_current_build_id(index_root_path)
    for stale_dir in build_dirs[keep:]:
        if active_id and stale_dir.name == active_id:
            continue
        for child in stale_dir.iterdir():
            child.unlink(missing_ok=True)
        stale_dir.rmdir()


def build_literature_faiss_index(
    session: Session,
    settings: ResolvedLiteratureRetrievalSettings,
    embedding_provider: LiteratureEmbeddingProvider,
    *,
    force: bool = False,
    check_only: bool = False,
) -> IndexBuildSummary:
    root = index_root(settings)
    if not force and not is_index_stale(session, root, settings=settings):
        build_dir = resolve_active_build_dir(root)
        manifest = load_build_manifest(build_dir)
        corpus = manifest.get("corpus") or {}
        return IndexBuildSummary(
            build_id=str(manifest.get("build_id")),
            build_dir=build_dir,
            corpus_revision=int(corpus.get("revision", 0)),
            chunk_count=int(corpus.get("chunk_count", 0)),
            skipped=True,
        )

    if check_only:
        raise IndexStaleError("Literature FAISS index is stale or missing.")

    state = get_corpus_state(session)
    chunks = list(session.scalars(select(PaperChunk).order_by(PaperChunk.chunk_id)))
    content_checksum, ordered_chunk_ids_checksum, chunk_count = compute_chunk_checksums(chunks)
    corpus_revision = int(state.corpus_revision)
    build_id = _build_id_for_revision(corpus_revision, content_checksum)

    with index_build_lock(root):
        if not force and not is_index_stale(session, root, settings=settings):
            build_dir = resolve_active_build_dir(root)
            manifest = load_build_manifest(build_dir)
            corpus = manifest.get("corpus") or {}
            return IndexBuildSummary(
                build_id=str(manifest.get("build_id")),
                build_dir=build_dir,
                corpus_revision=int(corpus.get("revision", 0)),
                chunk_count=int(corpus.get("chunk_count", 0)),
                skipped=True,
            )

        builds_dir = _builds_dir(root)
        build_dir = builds_dir / build_id
        if build_dir.exists():
            raise RuntimeError(f"Build directory already exists: {build_dir}")
        build_dir.mkdir(parents=True, exist_ok=False)

        vector_index = FaissLiteratureVectorIndex.from_chunks(chunks, embedding_provider)
        vector_index.save(build_dir)
        chunk_ids = [str(chunk.chunk_id) for chunk in sorted(chunks, key=lambda c: str(c.chunk_id))]
        _write_id_map(build_dir, chunk_ids)

        manifest_payload = build_manifest_payload(
            build_id=build_id,
            corpus_revision=corpus_revision,
            chunk_count=chunk_count,
            content_checksum=content_checksum,
            ordered_chunk_ids_checksum=ordered_chunk_ids_checksum,
            settings=settings,
            embedding_dimension=vector_index.dimensions,
        )
        (build_dir / "manifest.json").write_text(
            json.dumps(manifest_payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        _atomic_replace_current(root, build_id)
        _prune_old_builds(root)

    return IndexBuildSummary(
        build_id=build_id,
        build_dir=build_dir,
        corpus_revision=corpus_revision,
        chunk_count=chunk_count,
        skipped=False,
    )
