from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import create_engine

from rhizonp.config import PROJECT_ROOT
from rhizonp.domain.models import Base
from rhizonp.evaluation.annotation import (
    BLIND_REVIEWER_COLUMNS,
    PROVENANCE_SIDECAR_COLUMNS,
    PooledAnnotationCandidate,
    SystemHitProvenance,
    export_annotation_candidates,
    export_pooled_annotation_candidates,
    import_annotation_labels,
    pooled_candidates_to_blind_rows,
    write_blind_reviewer_sheet,
    write_provenance_sidecar,
)
from rhizonp.evaluation.pool_config import DEFAULT_POOL_SYSTEMS, PoolSystemSpec
from rhizonp.evaluation.real_benchmark import load_real_benchmark
from rhizonp.ingestion.corpus import load_corpus_snapshot, normalized_records_from_snapshot
from rhizonp.ingestion.literature import ingest_literature_records
from rhizonp.storage.postgres import create_session_factory, session_scope

FIXTURE_CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "pubmed" / "corpus_snapshot.json"
REAL_BENCHMARK = PROJECT_ROOT / "data" / "eval" / "phase2_real_pubmed_benchmark.json"


def _ingest_fixture(session_factory) -> None:
    records = normalized_records_from_snapshot(load_corpus_snapshot(FIXTURE_CORPUS))
    with session_scope(session_factory) as session:
        ingest_literature_records(session, records)


def test_pooled_export_unions_multiple_systems_and_deduplicates() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    _ingest_fixture(session_factory)

    benchmark = load_real_benchmark(REAL_BENCHMARK)
    with session_scope(session_factory) as session:
        pooled = export_pooled_annotation_candidates(
            session,
            benchmark,
            pool_systems=DEFAULT_POOL_SYSTEMS,
            pool_depth=5,
        )

    assert pooled
    pmids_by_query: dict[str, set[str]] = {}
    for candidate in pooled:
        pmids_by_query.setdefault(candidate.query_id, set()).add(candidate.pmid)
        assert candidate.retrieval_systems
        assert candidate.provenance_hits
        assert len(candidate.provenance_hits) == len(candidate.retrieval_systems)

    # One row per (query_id, pmid)
    assert sum(len(pmids) for pmids in pmids_by_query.values()) == len(pooled)


def test_pooled_provenance_preserves_per_system_rank_and_score(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    _ingest_fixture(session_factory)

    benchmark = load_real_benchmark(REAL_BENCHMARK)
    with session_scope(session_factory) as session:
        pooled = export_pooled_annotation_candidates(session, benchmark, pool_depth=3)

    sidecar = write_provenance_sidecar(tmp_path / "sidecar.csv", pooled)
    with sidecar.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert set(rows[0]) == set(PROVENANCE_SIDECAR_COLUMNS)
    assert rows[0]["retrieval_system"]
    assert rows[0]["rank"]
    assert rows[0]["score"]


def test_blind_export_excludes_retrieval_provenance(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    _ingest_fixture(session_factory)

    benchmark = load_real_benchmark(REAL_BENCHMARK)
    with session_scope(session_factory) as session:
        pooled = export_pooled_annotation_candidates(session, benchmark, pool_depth=3)

    blind_path = write_blind_reviewer_sheet(tmp_path / "blind.csv", pooled)
    with blind_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert set(rows[0]) == set(BLIND_REVIEWER_COLUMNS)
    forbidden = {"retrieval_system", "rank", "score", "category", "source_url"}
    assert forbidden.isdisjoint(set(rows[0]))


def test_blind_label_import_joins_by_query_and_pmid(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    _ingest_fixture(session_factory)

    benchmark_copy = tmp_path / "benchmark.json"
    benchmark_copy.write_text(REAL_BENCHMARK.read_text(encoding="utf-8"), encoding="utf-8")

    blind_rows = pooled_candidates_to_blind_rows(
        [
            PooledAnnotationCandidate(
                query_id="RQ001",
                query_text="test",
                category="x",
                pmid="12345678",
                title="t",
                abstract="a",
                doi=None,
                source_url=None,
                retrieval_systems=("bm25",),
                provenance_hits=(
                    SystemHitProvenance(
                        retrieval_system="bm25",
                        rank=1,
                        score=1.0,
                    ),
                ),
            )
        ]
    )
    blind_rows[0]["grade"] = "2"
    blind_rows[0]["notes"] = "direct"

    blind_path = tmp_path / "blind.csv"
    with blind_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(BLIND_REVIEWER_COLUMNS))
        writer.writeheader()
        writer.writerows(blind_rows)

    with session_scope(session_factory) as session:
        updated, result = import_annotation_labels(session, benchmark_copy, blind_path)

    assert result.labels_imported == 1
    labeled = next(query for query in updated.queries if query.query_id == "RQ001")
    assert labeled.labels[0].pmid == "12345678"
    assert labeled.labels[0].grade == 2


def test_legacy_single_system_export_remains_available() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    _ingest_fixture(session_factory)

    benchmark = load_real_benchmark(REAL_BENCHMARK)
    with session_scope(session_factory) as session:
        legacy = export_annotation_candidates(session, benchmark, top_k=3)

    assert legacy
    assert all(candidate.retrieval_system == "hybrid_hash" for candidate in legacy)


def test_custom_pool_system_list_is_configurable() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    _ingest_fixture(session_factory)

    benchmark = load_real_benchmark(REAL_BENCHMARK)
    custom_pool = (PoolSystemSpec(system_name="bm25", retrieval_mode="bm25"),)
    with session_scope(session_factory) as session:
        pooled = export_pooled_annotation_candidates(
            session,
            benchmark,
            pool_systems=custom_pool,
            pool_depth=3,
        )

    assert pooled
    assert all(hit.retrieval_system == "bm25" for candidate in pooled for hit in candidate.provenance_hits)
