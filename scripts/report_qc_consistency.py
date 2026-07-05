#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report QC duplicate judgment consistency.")
    parser.add_argument(
        "--review",
        type=Path,
        required=True,
        help="Reviewed blind reviewer CSV.",
    )
    parser.add_argument(
        "--qc-audit",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "annotation" / "qc_audit_mapping.csv",
        help="Private QC audit mapping CSV from export.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "reports" / "qc_consistency_report.json",
    )
    return parser.parse_args()


def main() -> None:
    import csv

    from rhizonp.evaluation.annotation import (
        QCAuditMapping,
        _load_review_rows,
        report_qc_consistency,
    )

    args = parse_args()
    review_rows = _load_review_rows(args.review)
    mappings: list[QCAuditMapping] = []
    if args.qc_audit.is_file():
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

    report = report_qc_consistency(review_rows, mappings)
    payload = {
        "pair_count": report.pair_count,
        "exact_agreement_count": report.exact_agreement_count,
        "exact_agreement_rate": report.exact_agreement_rate,
        "weighted_agreement_rate": report.weighted_agreement_rate,
        "metric_notes": {
            "weighted_agreement_rate": (
                "Mean of 1 - abs(source_grade - qc_grade) / 2 across QC pairs; "
                "not Cohen's weighted kappa."
            ),
        },
        "pairs": list(report.pairs),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(
        f"QC consistency: {report.exact_agreement_count}/{report.pair_count} exact, "
        f"weighted_agreement_rate={report.weighted_agreement_rate:.3f} -> {args.output}"
    )


if __name__ == "__main__":
    main()
