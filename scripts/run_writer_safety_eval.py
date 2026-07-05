#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main() -> None:
    from rhizonp.evaluation.writer_safety_benchmark import (
        run_writer_safety_benchmark,
        write_writer_safety_reports,
    )

    report = run_writer_safety_benchmark()
    json_path, md_path = write_writer_safety_reports(report)
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    if report.failed_count:
        raise SystemExit(f"Writer safety benchmark failed: {report.failed_count} case(s).")


if __name__ == "__main__":
    main()
