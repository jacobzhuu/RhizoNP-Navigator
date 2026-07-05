#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
DEFAULT_PHASE2_FIXTURE_PATH = PROJECT_ROOT / "data" / "fixtures" / "phase2_literature_demo.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load synthetic Phase 2 literature fixtures.")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_PHASE2_FIXTURE_PATH,
        help="Path to a Phase 2 literature fixture JSON file.",
    )
    return parser.parse_args()


def main() -> None:
    from rhizonp.ingestion.literature import load_phase2_literature_fixture
    from rhizonp.storage.postgres import (
        create_engine_from_settings,
        create_session_factory,
        session_scope,
    )

    args = parse_args()
    engine = create_engine_from_settings()
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        summary = load_phase2_literature_fixture(session, args.fixture)

    print(f"Loaded synthetic Phase 2 literature fixture: {summary}")


if __name__ == "__main__":
    main()
