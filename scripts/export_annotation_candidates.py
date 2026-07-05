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
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=PROJECT_ROOT / "data" / "snapshots" / "pubmed" / "rhizonp_domain_v1" / "corpus.json",
    )
    parser.add_argument(
        "--blind-output",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "annotation" / "blind_reviewer_sheet.csv",
    )
    parser.add_argument(
        "--provenance-output",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "annotation" / "provenance_sidecar.csv",
    )
    parser.add_argument(
        "--qc-audit-output",
        type=Path,
        default=PROJECT_ROOT / "data" / "eval" / "annotation" / "qc_audit_mapping.csv",
    )
    parser.add_argument(
        "--pool-depth",
        type=int,
        default=20,
    )
    parser.add_argument(
        "--shuffle-seed",
        type=int,
        default=20260705,
        help="Deterministic seed for within-query blind ordering.",
    )
    parser.add_argument(
        "--qc-fraction",
        type=float,
        default=0.0,
        help="Optional fraction of primary items to duplicate for QC (0 disables).",
    )
    parser.add_argument(
        "--qc-seed",
        type=int,
        default=20260705,
        help="Deterministic seed for QC duplicate selection.",
    )
    parser.add_argument(
        "--legacy-output",
        type=Path,
        default=None,
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.domain.models import Base
    from rhizonp.evaluation.annotation import (
        export_annotation_candidates,
        export_pooled_annotation_candidates,
        prepare_blind_annotation_export,
        write_annotation_export_csv,
        write_blind_reviewer_sheet,
        write_provenance_sidecar,
        write_qc_audit_mapping,
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

    export_bundle = prepare_blind_annotation_export(
        pooled,
        shuffle_seed=args.shuffle_seed,
        qc_fraction=args.qc_fraction,
        qc_seed=args.qc_seed,
    )
    blind_path = write_blind_reviewer_sheet(args.blind_output, export_bundle)
    provenance_path = write_provenance_sidecar(args.provenance_output, export_bundle)
    qc_path = write_qc_audit_mapping(args.qc_audit_output, export_bundle.qc_mappings)

    print(
        f"Exported {len(export_bundle.items)} blind items "
        f"({len(pooled)} primary pooled candidates"
        f"{f', {len(export_bundle.qc_mappings)} QC duplicates' if export_bundle.qc_mappings else ''})"
    )
    print(f"Blind sheet -> {blind_path}")
    print(f"Provenance sidecar -> {provenance_path}")
    if qc_path is not None:
        print(f"QC audit mapping -> {qc_path} (not for reviewers)")

    if args.legacy_output is not None:
        with session_scope(session_factory) as session:
            legacy = export_annotation_candidates(session, benchmark, top_k=args.pool_depth)
        legacy_path = write_annotation_export_csv(args.legacy_output, legacy)
        print(f"Legacy single-system export -> {legacy_path}")


if __name__ == "__main__":
    main()
