#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export pooled retrieval candidates for blind human relevance annotation.",
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
        "--blind-output",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "annotation" / "blind_reviewer_sheet.csv",
        help="Blind reviewer CSV without retrieval provenance.",
    )
    parser.add_argument(
        "--provenance-output",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "annotation" / "provenance_sidecar.csv",
        help="Provenance sidecar CSV with system/rank/score.",
    )
    parser.add_argument(
        "--pool-depth",
        type=int,
        default=20,
        help="Top-k depth per retrieval system before union.",
    )
    parser.add_argument(
        "--legacy-output",
        type=Path,
        default=None,
        help="Optional legacy single-system CSV export path.",
    )
    parser.add_argument(
        "--legacy-system",
        default="hybrid_hash",
        help="Legacy export system label when --legacy-output is set.",
    )
    parser.add_argument(
        "--legacy-mode",
        default="hybrid",
        help="Legacy export retrieval mode when --legacy-output is set.",
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.domain.models import Base
    from rhizonp.evaluation.annotation import (
        export_annotation_candidates,
        export_pooled_annotation_candidates,
        write_annotation_export_csv,
        write_blind_reviewer_sheet,
        write_provenance_sidecar,
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
        pooled = export_pooled_annotation_candidates(
            session,
            benchmark,
            pool_depth=args.pool_depth,
        )

    blind_path = write_blind_reviewer_sheet(args.blind_output, pooled)
    provenance_path = write_provenance_sidecar(args.provenance_output, pooled)
    print(
        f"Exported {len(pooled)} pooled candidates -> blind={blind_path}, "
        f"provenance={provenance_path}"
    )

    if args.legacy_output is not None:
        with session_scope(session_factory) as session:
            legacy = export_annotation_candidates(
                session,
                benchmark,
                retrieval_system=args.legacy_system,
                retrieval_mode=args.legacy_mode,
                top_k=args.pool_depth,
            )
        legacy_path = write_annotation_export_csv(args.legacy_output, legacy)
        print(f"Legacy single-system export -> {legacy_path}")


if __name__ == "__main__":
    main()
