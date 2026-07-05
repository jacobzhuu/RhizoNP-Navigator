#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main() -> None:
    from rhizonp.evaluation.scientific_constraint_benchmark import (
        run_scientific_constraint_benchmark,
        write_scientific_constraint_reports,
    )

    report = run_scientific_constraint_benchmark()
    json_path, md_path = write_scientific_constraint_reports(report)
    print(json.dumps(report.to_dict(), indent=2))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    if not report.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
