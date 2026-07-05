from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Grade taxonomy-aware evidence between a query taxon and literature taxon.",
    )
    parser.add_argument("query_taxon", help="Query/observation taxon label.")
    parser.add_argument("literature_taxon", help="Literature or database producer taxon label.")
    parser.add_argument(
        "--observation-method",
        default=None,
        help="Observation method, e.g. synthetic_16S_fixture.",
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        default=None,
        help="Optional taxonomy mapping fixture path.",
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.taxonomy.grading import grade_evidence

    args = parse_args()
    result = grade_evidence(
        args.query_taxon,
        args.literature_taxon,
        observation_method=args.observation_method,
        mapping_path=str(args.mapping) if args.mapping else None,
    )
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
