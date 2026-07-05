#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate RhizoNP workflows against PostgreSQL full stack.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="PostgreSQL DATABASE_URL (defaults to env or Docker Compose default).",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=PROJECT_ROOT / "data" / "snapshots" / "pubmed" / "rhizonp_domain_v1" / "corpus.json",
        help="Bounded PubMed corpus snapshot JSON.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "reports" / "latest",
        help="Report output directory.",
    )
    parser.add_argument(
        "--skip-restart",
        action="store_true",
        help="Skip non-destructive PostgreSQL container restart persistence check.",
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.evaluation.postgresql_fullstack_validation import (
        inspect_docker_state,
        run_postgresql_fullstack_validation,
        write_postgresql_validation_reports,
    )

    args = parse_args()
    if not args.snapshot.is_file():
        raise SystemExit(
            f"Corpus snapshot not found: {args.snapshot}. "
            "Run `make fetch-domain-corpus` or restore local corpus.json."
        )

    docker = inspect_docker_state()
    print(f"Docker state: {docker.classification}")

    report = run_postgresql_fullstack_validation(
        snapshot_path=args.snapshot,
        database_url=args.database_url,
        skip_restart=args.skip_restart,
    )
    json_path, md_path = write_postgresql_validation_reports(report, args.output_dir)

    corpus = report.corpus
    print(f"Database backend: {report.database_backend}")
    print(f"Migration: {report.migration_revision}")
    print(f"Papers: {corpus.get('paper_count', 0)}")
    print(f"Chunks: {corpus.get('chunk_count', 0)}")
    print(f"Own-data persisted: {report.own_data_persistence.get('persisted')}")
    print(f"Real trace present: {report.real_trace_present}")
    print(f"Restart persistence: {report.restart_persistence.get('persisted')}")
    print(f"API checks passed: {report.api_checks.get('passed')}")
    print(f"Overall passed: {report.passed}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")

    if not report.passed:
        raise SystemExit("PostgreSQL full-stack validation failed.")


if __name__ == "__main__":
    main()
