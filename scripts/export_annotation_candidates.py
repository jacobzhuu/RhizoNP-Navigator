#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export retrieval candidates for human relevance annotation.",
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "phase2_real_pubmed_benchmark.json",
        help="Real PubMed benchmark JSON with query definitions.",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=PROJECT_ROOT / "data" / "snapshots" / "pubmed" / "rhizonp_domain_v1" / "corpus.json",
        help="Corpus snapshot to ingest before export (offline).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "annotation" / "candidates.csv",
        help="CSV export path for human review.",
    )
    parser.add_argument(
        "--format",
        choices=("csv", "json"),
        default="csv",
        help="Export format.",
    )
    parser.add_argument(
        "--retrieval-system",
        default="hybrid_hash",
        help="Label for the retrieval system used to generate candidates.",
    )
    parser.add_argument(
        "--retrieval-mode",
        default="hybrid",
        help="Retrieval mode passed to search_paper_chunks.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=20,
        help="Number of candidates per query.",
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.domain.models import Base
    from rhizonp.evaluation.annotation import (
        export_annotation_candidates,
        write_annotation_export_csv,
        write_annotation_export_json,
    )
    from rhizonp.evaluation.real_benchmark import load_real_benchmark
    from rhizonp.ingestion.corpus import load_corpus_snapshot, normalized_records_from_snapshot
    from rhizonp.ingestion.literature import ingest_literature_records
    from rhizonp.storage.postgres import (
        create_engine_from_settings,
        create_session_factory,
        session_scope,
    )

    args = parse_args()
    benchmark = load_real_benchmark(args.benchmark)
    snapshot = load_corpus_snapshot(args.corpus)
    records = normalized_records_from_snapshot(snapshot)

    engine = create_engine_from_settings()
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        ingest_literature_records(session, records)
        candidates = export_annotation_candidates(
            session,
            benchmark,
            retrieval_system=args.retrieval_system,
            retrieval_mode=args.retrieval_mode,
            top_k=args.top_k,
        )

    if args.format == "json":
        output_path = write_annotation_export_json(args.output, candidates)
    else:
        output_path = write_annotation_export_csv(args.output, candidates)

    print(f"Exported {len(candidates)} annotation candidates -> {output_path}")


if __name__ == "__main__":
    main()
