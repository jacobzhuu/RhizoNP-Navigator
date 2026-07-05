#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch a bounded NPAtlas metadata snapshot (requires network).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "snapshots" / "npatlas" / "rhizonp_domain_v1",
        help="Directory for snapshot.json and manifest.json.",
    )
    parser.add_argument(
        "--snapshot-id",
        default="rhizonp_domain_v1",
        help="Snapshot identifier written into metadata/manifest.",
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.ingestion.npatlas import (
        DEFAULT_BOUNDED_TAXA,
        NPAtlasHttpAdapter,
        fetch_bounded_npatlas_records,
        snapshot_from_records,
        write_npatlas_snapshot,
    )

    args = parse_args()
    adapter = NPAtlasHttpAdapter()
    records = fetch_bounded_npatlas_records(adapter, DEFAULT_BOUNDED_TAXA)
    snapshot = snapshot_from_records(
        records,
        snapshot_id=args.snapshot_id,
        description=(
            "Bounded NPAtlas snapshot for Streptomyces/Bacillus genus compounds "
            "used by RhizoNP Navigator offline linking."
        ),
    )
    output_path = write_npatlas_snapshot(snapshot, args.output_dir)
    print(f"Wrote {len(records)} NPAtlas records to {output_path}")


if __name__ == "__main__":
    main()
