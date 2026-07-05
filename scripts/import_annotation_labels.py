#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import human-reviewed 0/1/2 relevance labels into the real benchmark.",
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "phase2_real_pubmed_benchmark.json",
        help="Real PubMed benchmark JSON to update.",
    )
    parser.add_argument(
        "--review",
        type=Path,
        required=True,
        help="Reviewed CSV or JSON with grade labels.",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=PROJECT_ROOT / "data" / "snapshots" / "pubmed" / "rhizonp_domain_v1" / "corpus.json",
        help="Corpus snapshot used to validate PMIDs (offline).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output benchmark path (defaults to in-place update).",
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.domain.models import Base
    from rhizonp.evaluation.annotation import import_annotation_labels
    from rhizonp.ingestion.corpus import load_corpus_snapshot, normalized_records_from_snapshot
    from rhizonp.ingestion.literature import ingest_literature_records
    from rhizonp.storage.postgres import (
        create_engine_from_settings,
        create_session_factory,
        session_scope,
    )

    args = parse_args()
    snapshot = load_corpus_snapshot(args.corpus)
    records = normalized_records_from_snapshot(snapshot)

    engine = create_engine_from_settings()
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        ingest_literature_records(session, records)
        updated, result = import_annotation_labels(
            session,
            args.benchmark,
            args.review,
            output_path=args.output,
        )

    print(
        "Imported labels: "
        f"{result.labels_imported} labels across {result.queries_updated} queries; "
        f"annotation_status={updated.queries and 'see benchmark file'}"
    )
    if result.duplicate_labels:
        print(f"Duplicates skipped: {', '.join(result.duplicate_labels)}")
    if result.unknown_pmids:
        print(f"Unknown PMIDs rejected: {', '.join(result.unknown_pmids)}")


if __name__ == "__main__":
    main()
