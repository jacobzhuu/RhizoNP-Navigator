#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch or ingest a bounded PubMed domain literature corpus.",
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "domain_corpus_queries.json",
        help="Path to corpus query configuration JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path for single-file corpus snapshot JSON (legacy mode).",
    )
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "snapshots" / "pubmed" / "rhizonp_domain_v1",
        help="Directory for versioned corpus snapshot with manifest.",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Fetch metadata from PubMed E-utilities and write a corpus snapshot.",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Ingest a saved corpus snapshot into the configured database.",
    )
    return parser.parse_args()


def _resolve_corpus_path(args: argparse.Namespace) -> Path:
    if args.output is not None:
        return args.output
    snapshot_corpus = args.snapshot_dir / "corpus.json"
    if snapshot_corpus.is_file():
        return snapshot_corpus
    return PROJECT_ROOT / "data" / "processed" / "pubmed_corpus" / "rhizonp_domain_v1.json"


def main() -> None:
    from rhizonp.config import get_settings
    from rhizonp.ingestion.corpus import (
        corpus_snapshot_from_records,
        fetch_domain_corpus,
        load_corpus_query_config,
        load_corpus_snapshot,
        normalized_records_from_snapshot,
        save_corpus_snapshot,
        save_versioned_corpus_snapshot,
        verify_corpus_snapshot_directory,
    )
    from rhizonp.ingestion.literature import ingest_literature_records
    from rhizonp.literature.pubmed_adapter import PubMedEutilitiesAdapter
    from rhizonp.storage.postgres import (
        create_engine_from_settings,
        create_session_factory,
        session_scope,
    )

    args = parse_args()
    if args.fetch == args.ingest:
        raise SystemExit("Specify exactly one of --fetch or --ingest.")

    if args.fetch:
        config = load_corpus_query_config(args.queries)
        config = {
            **config,
            "query_config_path": str(args.queries.resolve()),
        }
        settings = get_settings()
        per_query_retmax = int(config.get("default_retmax", 12))
        adapter = PubMedEutilitiesAdapter(
            max_results=max(per_query_retmax, settings.ncbi_max_results),
        )
        records, metadata = fetch_domain_corpus(adapter, config)
        snapshot = corpus_snapshot_from_records(records, metadata=metadata)

        corpus_path, manifest_path, pmid_list_path = save_versioned_corpus_snapshot(
            snapshot,
            args.snapshot_dir,
            query_config_path=args.queries,
        )
        verify_corpus_snapshot_directory(args.snapshot_dir)

        if args.output is not None:
            save_corpus_snapshot(snapshot, args.output)

        print(
            "Fetched PubMed corpus snapshot: "
            f"{metadata['record_count']} records -> {corpus_path}"
        )
        print(f"Manifest: {manifest_path}")
        print(f"PMID list: {pmid_list_path}")
        return

    corpus_path = _resolve_corpus_path(args)
    if corpus_path.parent.name != "pubmed" and (corpus_path.parent / "manifest.json").is_file():
        verify_corpus_snapshot_directory(corpus_path.parent)

    snapshot = load_corpus_snapshot(corpus_path)
    records = normalized_records_from_snapshot(snapshot)
    engine = create_engine_from_settings()
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        summary = ingest_literature_records(session, records)
    print(f"Ingested corpus snapshot from {corpus_path}: {summary}")


if __name__ == "__main__":
    main()
