#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline Phase 2 retrieval benchmark.")
    parser.add_argument(
        "--gold",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "phase2_retrieval_gold.json",
        help="Path to synthetic retrieval gold benchmark JSON.",
    )
    parser.add_argument(
        "--real-benchmark",
        type=Path,
        default=None,
        help="Path to real PubMed benchmark JSON (paper-level PMID labels).",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=None,
        help="Corpus snapshot for real benchmark evaluation (offline).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path for benchmark report JSON output.",
    )
    parser.add_argument(
        "--include-model-dense",
        action="store_true",
        help="Include model-backed dense/hybrid systems when dependencies are available.",
    )
    parser.add_argument(
        "--include-bge-rerank",
        action="store_true",
        help="Include BGE reranker systems when dependencies are available.",
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.domain.models import Base
    from rhizonp.evaluation.real_benchmark import (
        load_real_benchmark,
        real_benchmark_report_to_dict,
        run_real_retrieval_benchmark,
    )
    from rhizonp.evaluation.retrieval_benchmark import (
        benchmark_report_to_dict,
        load_retrieval_benchmark,
        run_retrieval_benchmark,
    )
    from rhizonp.ingestion.corpus import load_corpus_snapshot, normalized_records_from_snapshot
    from rhizonp.ingestion.literature import (
        ingest_literature_records,
        load_phase2_literature_fixture,
    )
    from rhizonp.storage.postgres import (
        create_engine_from_settings,
        create_session_factory,
        session_scope,
    )

    args = parse_args()
    try:
        engine = create_engine_from_settings()
    except RuntimeError as exc:
        if "DATABASE_URL" not in str(exc):
            raise
        from sqlalchemy import create_engine
        from sqlalchemy.pool import StaticPool

        print(
            "DATABASE_URL is not configured; using in-memory SQLite for offline retrieval eval."
        )
        engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    if args.real_benchmark is not None:
        benchmark = load_real_benchmark(args.real_benchmark)
        corpus_path = args.corpus or (
            PROJECT_ROOT / "data" / "snapshots" / "pubmed" / "rhizonp_domain_v1" / "corpus.json"
        )
        snapshot = load_corpus_snapshot(corpus_path)
        records = normalized_records_from_snapshot(snapshot)
        output_path = args.output or (
            PROJECT_ROOT
            / "data"
            / "eval"
            / "reports"
            / "latest"
            / "phase2_real_retrieval_report.json"
        )

        with session_scope(session_factory) as session:
            ingest_literature_records(session, records)
            report = run_real_retrieval_benchmark(
                session,
                benchmark,
                include_model_dense=args.include_model_dense,
                include_bge_rerank=args.include_bge_rerank,
            )

        if report.labeled_query_count == 0:
            print(
                "Real benchmark has no human labels yet; "
                "export candidates, annotate, and import labels before evaluation."
            )
            report_dict = real_benchmark_report_to_dict(report)
        else:
            report_dict = real_benchmark_report_to_dict(report)
    else:
        benchmark = load_retrieval_benchmark(args.gold)
        output_path = args.output or (
            PROJECT_ROOT
            / "data"
            / "eval"
            / "reports"
            / "latest"
            / "phase2_retrieval_report.json"
        )
        with session_scope(session_factory) as session:
            load_phase2_literature_fixture(session)
            report = run_retrieval_benchmark(
                session,
                benchmark,
                include_model_dense=args.include_model_dense,
                include_bge_rerank=args.include_bge_rerank,
            )
        report_dict = benchmark_report_to_dict(report)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report_dict, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Wrote retrieval benchmark report to {output_path}")


if __name__ == "__main__":
    main()
