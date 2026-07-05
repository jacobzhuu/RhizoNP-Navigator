#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit lexical overlap between corpus and benchmark queries.",
    )
    parser.add_argument(
        "--corpus-queries",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "domain_corpus_queries.json",
        help="Corpus query configuration JSON.",
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "phase2_real_pubmed_benchmark.json",
        help="Real benchmark query JSON.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "reports" / "corpus_benchmark_leakage_audit.json",
        help="Machine-readable audit report path.",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "reports" / "corpus_benchmark_leakage_audit.md",
        help="Markdown audit report path.",
    )
    parser.add_argument(
        "--token-overlap-threshold",
        type=float,
        default=0.6,
        help="Token Jaccard threshold for lexical warnings.",
    )
    parser.add_argument(
        "--sequence-similarity-threshold",
        type=float,
        default=0.75,
        help="Normalized sequence similarity threshold for lexical warnings.",
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.evaluation.leakage_audit import run_leakage_audit, write_leakage_audit_reports

    args = parse_args()
    report = run_leakage_audit(
        args.corpus_queries,
        args.benchmark,
        token_overlap_threshold=args.token_overlap_threshold,
        sequence_similarity_threshold=args.sequence_similarity_threshold,
    )
    json_path, markdown_path = write_leakage_audit_reports(
        report,
        json_path=args.json_output,
        markdown_path=args.markdown_output,
    )
    print(
        "Leakage audit complete: "
        f"{len(report.exact_duplicates)} exact, "
        f"{len(report.normalized_duplicates)} normalized, "
        f"{len(report.high_token_overlap)} token-overlap, "
        f"{len(report.high_sequence_similarity)} sequence-similarity warnings."
    )
    print(f"JSON report -> {json_path}")
    print(f"Markdown report -> {markdown_path}")


if __name__ == "__main__":
    main()
