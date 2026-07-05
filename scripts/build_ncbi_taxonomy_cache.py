#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch a bounded NCBI Taxonomy cache (requires network).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "snapshots" / "taxonomy" / "ncbi_bounded_v1",
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.taxonomy.ncbi_resolver import (
        NCBITaxonomyClient,
        cache_payload_from_records,
        fetch_bounded_ncbi_taxonomy_records,
        write_ncbi_taxonomy_cache,
    )

    args = parse_args()
    client = NCBITaxonomyClient()
    records = fetch_bounded_ncbi_taxonomy_records(client)
    payload = cache_payload_from_records(records)
    path = write_ncbi_taxonomy_cache(payload, args.output_dir)
    print(f"Wrote {len(records)} NCBI taxonomy entries to {path}")


if __name__ == "__main__":
    main()
