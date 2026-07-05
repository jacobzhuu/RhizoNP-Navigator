#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RhizoNP end-to-end evaluation suite.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "end_to_end_cases.json",
        help="Path to end-to-end evaluation cases.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "reports" / "latest",
        help="Directory for JSON and Markdown reports.",
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.evaluation.end_to_end import run_end_to_end_evaluation, write_evaluation_reports

    args = parse_args()
    report = run_end_to_end_evaluation(args.cases)
    json_path, md_path = write_evaluation_reports(report, args.output_dir)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Retrieval Recall@10: {report.retrieval['recall_at_10']:.4f}")


if __name__ == "__main__":
    main()
