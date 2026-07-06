#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or validate the literature FAISS index.")
    parser.add_argument(
        "--if-stale",
        action="store_true",
        help="Rebuild only when the active index is missing or stale (default when no mode flag).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force a full rebuild even when the active index is current.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Exit with code 1 when the index is stale or missing; otherwise print OK.",
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.literature.corpus_state import ensure_corpus_state
    from rhizonp.literature.embeddings import create_literature_embedding_provider
    from rhizonp.literature.index_store import IndexStaleError, build_literature_faiss_index
    from rhizonp.literature.retrieval_settings import resolve_literature_retrieval_settings
    from rhizonp.storage.postgres import (
        create_engine_from_settings,
        create_session_factory,
        session_scope,
    )

    args = parse_args()
    settings = resolve_literature_retrieval_settings()
    if settings.vector_index_backend != "faiss":
        print(
            f"Skipping FAISS build: vector_index_backend={settings.vector_index_backend!r} "
            f"(profile={settings.profile!r})"
        )
        return

    engine = create_engine_from_settings()
    session_factory = create_session_factory(engine)
    embedding_provider = create_literature_embedding_provider(
        provider=settings.embedding_provider,
        hashing_dimensions=settings.hashing_dimensions,
        model_name=settings.embedding_model,
    )

    with session_scope(session_factory) as session:
        ensure_corpus_state(session)
        try:
            summary = build_literature_faiss_index(
                session,
                settings,
                embedding_provider,
                force=args.force,
                check_only=args.check_only,
            )
        except IndexStaleError as exc:
            print(f"STALE: {exc}")
            raise SystemExit(1) from exc

    if summary.skipped:
        print(
            f"Literature FAISS index up to date: build_id={summary.build_id} "
            f"corpus_revision={summary.corpus_revision} chunks={summary.chunk_count}"
        )
        return

    print(
        f"Built literature FAISS index: build_id={summary.build_id} "
        f"corpus_revision={summary.corpus_revision} chunks={summary.chunk_count} "
        f"path={summary.build_dir}"
    )


if __name__ == "__main__":
    main()
