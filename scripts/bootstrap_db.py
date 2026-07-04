#!/usr/bin/env python3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main() -> None:
    from rhizonp.domain.models import Base
    from rhizonp.storage.postgres import create_engine_from_settings

    engine = create_engine_from_settings()
    Base.metadata.create_all(engine)
    print("Database schema created from SQLAlchemy metadata.")


if __name__ == "__main__":
    main()
