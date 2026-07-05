#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main() -> None:
    from rhizonp.ingestion.npatlas import (
        DEFAULT_NPATLAS_SNAPSHOT_PATH,
        load_bounded_npatlas_snapshot,
    )
    from rhizonp.linking.candidate_engine import link_natural_product_candidates
    from rhizonp.linking.np_adapter import NaturalProductSource, load_bounded_npatlas_records

    if not DEFAULT_NPATLAS_SNAPSHOT_PATH.is_file():
        raise SystemExit(f"Missing NPAtlas snapshot: {DEFAULT_NPATLAS_SNAPSHOT_PATH}")

    load_bounded_npatlas_records.cache_clear()
    normalized = load_bounded_npatlas_snapshot()
    fixture_records = load_bounded_npatlas_records()

    structured_count = sum(
        1
        for record in normalized
        if record.bioactivity
        and record.bioactivity.get("evidence_level") == "origin_reference_reported"
    )
    summary_count = sum(1 for record in normalized if record.bioactivity_summary)
    fixture_bio_count = sum(1 for record in fixture_records if record.bioactivity is not None)

    matrix = link_natural_product_candidates(
        "Streptomyces",
        observation_method="synthetic_16S_fixture",
        record_source=NaturalProductSource.NPATLAS_BOUNDED,
    )
    rows_with_bioactivity = sum(1 for row in matrix.rows if row.bioactivity is not None)
    sample = matrix.rows[0] if matrix.rows else None

    report = {
        "validation_id": "npatlas_bioactivity_v1",
        "disclaimer": (
            "Bioactivity fields are derived from NPAtlas origin-reference titles only; "
            "this is not assay-validated bioactivity or empirical scientific validation."
        ),
        "snapshot_path": str(DEFAULT_NPATLAS_SNAPSHOT_PATH),
        "record_count": len(normalized),
        "bioactivity_summary_coverage": summary_count / max(len(normalized), 1),
        "structured_bioactivity_count": structured_count,
        "fixture_bioactivity_count": fixture_bio_count,
        "candidate_rows_with_bioactivity": rows_with_bioactivity,
        "sample_row": {
            "compound_name": sample.compound_name if sample else None,
            "bioactivity": sample.bioactivity if sample else None,
            "score": sample.score if sample else None,
            "provenance_source": sample.provenance.get("source") if sample else None,
        },
        "limitations": [
            "NPAtlas compound API does not expose structured bioactivity assay records.",
            "Derived activity types are conservative title-keyword extractions only.",
            "Bioactivity metadata does not affect candidate ranking scores.",
        ],
        "passed": (
            len(normalized) >= 10
            and summary_count == len(normalized)
            and fixture_bio_count == len(normalized)
            and rows_with_bioactivity >= 1
            and sample is not None
            and sample.bioactivity is not None
            and sample.provenance.get("source") == "npatlas"
        ),
    }

    output_dir = PROJECT_ROOT / "data" / "eval" / "reports" / "latest"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "npatlas_bioactivity_validation.json"
    md_path = output_dir / "npatlas_bioactivity_validation.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# NPAtlas Bounded Bioactivity Validation",
                "",
                report["disclaimer"],
                "",
                f"- Record count: **{report['record_count']}**",
                f"- Bioactivity summary coverage: **{report['bioactivity_summary_coverage']:.2%}**",
                f"- Structured bioactivity records: **{report['structured_bioactivity_count']}**",
                f"- Candidate rows with bioactivity: **{report['candidate_rows_with_bioactivity']}**",
                f"- Passed: **{report['passed']}**",
                "",
                "## Limitations",
                "",
                *[f"- {item}" for item in report["limitations"]],
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
