#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "fixtures" / "own_data_demo"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "own_data_demo"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run own-data-to-literature linking pipeline.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing taxa.csv, metabolites.csv, associations.csv.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and CSV exports.",
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.omics.pipeline import (
        export_candidate_matrix_csv,
        export_pipeline_json,
        run_own_data_pipeline,
    )

    args = parse_args()
    result = run_own_data_pipeline(args.data_dir)
    json_path = export_pipeline_json(result, args.output_dir / "pipeline_result.json")
    csv_path = export_candidate_matrix_csv(result, args.output_dir / "candidate_matrix.csv")
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    print(f"Processed {len(result.association_results)} associations")


if __name__ == "__main__":
    main()
