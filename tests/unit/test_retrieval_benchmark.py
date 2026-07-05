from __future__ import annotations

from sqlalchemy import create_engine, select

from rhizonp.config import PROJECT_ROOT
from rhizonp.domain.models import Base, PaperChunk
from rhizonp.evaluation.retrieval_benchmark import (
    load_retrieval_benchmark,
    run_retrieval_benchmark,
)
from rhizonp.ingestion.literature import load_phase2_literature_fixture
from rhizonp.storage.postgres import create_session_factory, session_scope


def test_retrieval_benchmark_runs_offline_on_synthetic_gold() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    gold_path = PROJECT_ROOT / "data" / "eval" / "phase2_retrieval_gold.json"
    benchmark = load_retrieval_benchmark(gold_path)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)
        report = run_retrieval_benchmark(session, benchmark)

    assert report.benchmark_id == "phase2_synthetic_mini"
    system_names = {system.system_name for system in report.systems}
    assert system_names == {
        "bm25",
        "dense_hash",
        "hybrid_hash",
        "hybrid_rerank_lexical",
    }

    bm25 = next(system for system in report.systems if system.system_name == "bm25")
    assert bm25.recall_at_5 > 0.0
    assert bm25.mrr_at_10 > 0.0
    assert "Q001" in bm25.per_query


def test_retrieval_benchmark_uses_source_hash_trace_keys() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        load_phase2_literature_fixture(session)
        chunk = session.scalar(
            select(PaperChunk).where(PaperChunk.section == "results").limit(1)
        )
        assert chunk is not None
        expected_hash = chunk.source_hash

    benchmark = load_retrieval_benchmark(PROJECT_ROOT / "data" / "eval" / "phase2_retrieval_gold.json")
    q001 = next(query for query in benchmark.queries if query.query_id == "Q001")
    assert expected_hash in q001.relevant_source_hashes
