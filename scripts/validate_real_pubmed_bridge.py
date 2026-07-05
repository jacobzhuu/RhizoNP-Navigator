#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate own-data bridge against bounded real PubMed corpus.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=PROJECT_ROOT / "data" / "snapshots" / "pubmed" / "rhizonp_domain_v1" / "corpus.json",
        help="Path to bounded PubMed corpus snapshot JSON.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Optional DATABASE_URL override (defaults to env or in-memory SQLite).",
    )
    parser.add_argument(
        "--retrieval-mode",
        default="bm25",
        help="Retrieval mode for validation queries.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Top-k for validation retrieval.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "reports" / "latest",
        help="Directory for validation reports.",
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.omics.real_pubmed_validation import (
        run_real_pubmed_validation,
        write_validation_reports,
    )

    args = parse_args()
    if not args.snapshot.is_file():
        raise SystemExit(
            f"Corpus snapshot not found: {args.snapshot}. "
            "Run `make fetch-domain-corpus` or restore local corpus.json."
        )

    report = run_real_pubmed_validation(
        snapshot_path=args.snapshot,
        database_url=args.database_url,
        retrieval_mode=args.retrieval_mode,
        top_k=args.top_k,
    )
    json_path, md_path = write_validation_reports(report, args.output_dir)

    corpus = report.corpus
    print(f"Corpus ID: {corpus.corpus_id}")
    print(f"Corpus type: {corpus.corpus_type}")
    print(f"Records ingested: {corpus.record_count}")
    print(f"Papers in DB: {corpus.paper_count}")
    print(f"Chunks in DB: {corpus.chunk_count}")
    print(f"PMID coverage: {corpus.pmid_coverage:.2%}")
    print(f"DOI coverage: {corpus.doi_coverage:.2%}")
    print(f"DB backend: {corpus.database_backend}")
    print(f"Real trace present: {report.real_trace_present}")
    if report.real_trace:
        trace = report.real_trace
        print(
            "Real trace: "
            f"query={trace.get('generated_query')} "
            f"pmid={trace.get('pmid')} "
            f"doi={trace.get('doi')}"
        )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")

    if not report.real_trace_present:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
