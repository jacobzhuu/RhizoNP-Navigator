#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
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
    )
    parser.add_argument(
        "--review",
        type=Path,
        required=True,
        help="Reviewed blind reviewer CSV or JSON with grade labels.",
    )
    parser.add_argument(
        "--qc-audit",
        type=Path,
        default=None,
        help="Optional QC audit mapping CSV; QC duplicate rows are excluded before import.",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=PROJECT_ROOT / "data" / "snapshots" / "pubmed" / "rhizonp_domain_v1" / "corpus.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.domain.models import Base
    from rhizonp.evaluation.annotation import (
        QCAuditMapping,
        _load_review_rows,
        filter_qc_rows_for_import,
        import_annotation_labels,
    )
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

    review_rows = _load_review_rows(args.review)
    if args.qc_audit is not None and args.qc_audit.is_file():
        mappings: list[QCAuditMapping] = []
        with args.qc_audit.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                mappings.append(
                    QCAuditMapping(
                        qc_annotation_item_id=str(row["qc_annotation_item_id"]),
                        source_annotation_item_id=str(row["source_annotation_item_id"]),
                        query_id=str(row["query_id"]),
                        pmid=str(row["pmid"]),
                    )
                )
        review_rows = filter_qc_rows_for_import(review_rows, mappings)

    engine = create_engine_from_settings()
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    review_path = args.review
    if args.qc_audit is not None and args.qc_audit.is_file():
        filtered_path = args.review.parent / f"{args.review.stem}.import_filtered.csv"
        import csv as csv_module

        if review_rows:
            with filtered_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv_module.DictWriter(handle, fieldnames=list(review_rows[0].keys()))
                writer.writeheader()
                writer.writerows(review_rows)
            review_path = filtered_path

    with session_scope(session_factory) as session:
        ingest_literature_records(session, records)
        updated, result = import_annotation_labels(
            session,
            args.benchmark,
            review_path,
            output_path=args.output,
        )

    print(
        "Imported labels: "
        f"{result.labels_imported} labels across {result.queries_updated} queries"
    )
    if result.duplicate_labels:
        print(f"Duplicates skipped: {', '.join(result.duplicate_labels)}")
    if result.unknown_pmids:
        print(f"Unknown PMIDs rejected: {', '.join(result.unknown_pmids)}")


if __name__ == "__main__":
    main()
