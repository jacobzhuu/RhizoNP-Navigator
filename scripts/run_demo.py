#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "demo"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RhizoNP Navigator offline demo cases.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for demo JSON/CSV/Markdown outputs.",
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.demo.runner import run_all_demos

    args = parse_args()
    result = run_all_demos(args.output_dir)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    print(f"\nDemo outputs written to {result.output_dir}")


if __name__ == "__main__":
    main()
