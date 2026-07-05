#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "fixtures" / "own_data_demo"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "own_data_demo"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run own-data-to-literature linking pipeline.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing taxa.csv, metabolites.csv, associations.csv.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and CSV exports.",
    )
    parser.add_argument(
        "--enable-literature",
        action="store_true",
        help="Enable DB-backed literature retrieval via search_paper_chunks.",
    )
    parser.add_argument(
        "--retrieval-mode",
        default="hybrid_rerank",
        help="Retrieval mode passed to search_paper_chunks.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Maximum literature hits per generated query.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Optional DATABASE_URL override for literature retrieval.",
    )
    return parser.parse_args()


def main() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from rhizonp.domain.models import Base
    from rhizonp.ingestion.literature import load_phase2_literature_fixture
    from rhizonp.omics.pipeline import (
        OwnDataPipelineOptions,
        export_candidate_matrix_csv,
        export_pipeline_json,
        run_own_data_pipeline,
    )
    from rhizonp.storage.postgres import create_engine_from_settings, create_session_factory

    args = parse_args()
    literature_session: Session | None = None
    if args.enable_literature:
        try:
            engine = create_engine_from_settings(args.database_url)
        except RuntimeError:
            engine = create_engine(
                "sqlite+pysqlite://",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                future=True,
            )
        Base.metadata.create_all(engine)
        session_factory = create_session_factory(engine)
        literature_session = session_factory()
        load_phase2_literature_fixture(literature_session)
        literature_session.commit()

    try:
        result = run_own_data_pipeline(
            args.data_dir,
            session=literature_session,
            options=OwnDataPipelineOptions(
                enable_literature_retrieval=args.enable_literature,
                retrieval_mode=args.retrieval_mode,
                top_k=args.top_k,
            ),
        )
    finally:
        if literature_session is not None:
            literature_session.close()

    json_path = export_pipeline_json(result, args.output_dir / "pipeline_result.json")
    csv_path = export_candidate_matrix_csv(result, args.output_dir / "candidate_matrix.csv")
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    print(f"Processed {len(result.association_results)} associations")
    if args.enable_literature:
        for item in result.association_results:
            literature = item.literature_retrieval
            print(
                f"  {item.association.association_id}: literature={literature.get('status')} "
                f"hits={len(literature.get('hits', []))}"
            )


if __name__ == "__main__":
    main()
