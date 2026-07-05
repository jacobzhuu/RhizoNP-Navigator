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
        default=PROJECT_ROOT / "data" / "processed" / "pubmed_corpus" / "rhizonp_domain_v1.json",
        help="Path for corpus snapshot JSON output or input.",
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


def main() -> None:
    from rhizonp.ingestion.corpus import (
        corpus_snapshot_from_records,
        fetch_domain_corpus,
        load_corpus_query_config,
        load_corpus_snapshot,
        normalized_records_from_snapshot,
        save_corpus_snapshot,
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
        adapter = PubMedEutilitiesAdapter()
        records, metadata = fetch_domain_corpus(adapter, config)
        snapshot = corpus_snapshot_from_records(records, metadata=metadata)
        output_path = save_corpus_snapshot(snapshot, args.output)
        print(
            f"Fetched PubMed corpus snapshot: {metadata['record_count']} records -> {output_path}"
        )
        return

    snapshot = load_corpus_snapshot(args.output)
    records = normalized_records_from_snapshot(snapshot)
    engine = create_engine_from_settings()
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        summary = ingest_literature_records(session, records)
    print(f"Ingested corpus snapshot from {args.output}: {summary}")


if __name__ == "__main__":
    main()
