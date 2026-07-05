from __future__ import annotations

import os
import shutil

import pytest
from sqlalchemy import create_engine, text

from rhizonp.evaluation.postgresql_fullstack_validation import run_postgresql_fullstack_validation


def _postgres_available() -> bool:
    if shutil.which("docker") is None:
        return False
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:rhizonp_dev@127.0.0.1:5432/postgres",
    )
    if not database_url.startswith("postgresql"):
        return False
    try:
        engine = create_engine(database_url, future=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL runtime unavailable")
def test_postgresql_fullstack_validation_passes() -> None:
    report = run_postgresql_fullstack_validation(skip_restart=True)
    assert report.database_backend == "postgresql"
    assert report.corpus.get("corpus_type") == "REAL_BOUNDED_PUBMED"
    assert report.corpus.get("paper_count", 0) >= 1
    assert report.read_back.get("dataset_found") is True
    assert report.real_trace_present is True
    assert report.passed is True
