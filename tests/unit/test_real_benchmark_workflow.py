from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import create_engine

from rhizonp.config import PROJECT_ROOT
from rhizonp.domain.models import Base
from rhizonp.evaluation.annotation import (
    export_annotation_candidates,
    import_annotation_labels,
    validate_imported_labels,
    write_annotation_export_csv,
)
from rhizonp.evaluation.real_benchmark import (
    benchmark_annotation_status,
    load_real_benchmark,
    run_real_retrieval_benchmark,
)
from rhizonp.ingestion.corpus import (
    load_corpus_snapshot,
    normalized_records_from_snapshot,
    save_versioned_corpus_snapshot,
    verify_corpus_snapshot_directory,
)
from rhizonp.ingestion.literature import ingest_literature_records
from rhizonp.storage.postgres import create_session_factory, session_scope

FIXTURE_CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "pubmed" / "corpus_snapshot.json"
REAL_BENCHMARK = PROJECT_ROOT / "data" / "eval" / "phase2_real_pubmed_benchmark.json"


def _ingest_fixture_corpus(session_factory) -> None:
    records = normalized_records_from_snapshot(load_corpus_snapshot(FIXTURE_CORPUS))
    with session_scope(session_factory) as session:
        ingest_literature_records(session, records)


def test_real_benchmark_template_has_no_fabricated_labels() -> None:
    benchmark = load_real_benchmark(REAL_BENCHMARK)
    assert benchmark.benchmark_type == "real_pubmed"
    assert len(benchmark.queries) == 18
    assert benchmark_annotation_status(benchmark) == "pending"
    assert all(not query.labels for query in benchmark.queries)


def test_export_annotation_candidates_from_fixture_corpus(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    _ingest_fixture_corpus(session_factory)

    benchmark = load_real_benchmark(REAL_BENCHMARK)
    with session_scope(session_factory) as session:
        candidates = export_annotation_candidates(session, benchmark, top_k=5)

    assert candidates
    assert all(candidate.pmid for candidate in candidates)
    assert all(candidate.query_id for candidate in candidates)

    output = write_annotation_export_csv(tmp_path / "candidates.csv", candidates)
    with output.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert rows[0]["grade"] == ""


def test_import_annotation_labels_validates_unknown_pmids_and_duplicates() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    _ingest_fixture_corpus(session_factory)

    benchmark = load_real_benchmark(REAL_BENCHMARK)
    review_rows = [
        {"query_id": "RQ001", "pmid": "12345678", "grade": "2", "annotator": "test"},
        {"query_id": "RQ001", "pmid": "12345678", "grade": "1", "annotator": "test"},
        {"query_id": "RQ002", "pmid": "99999999", "grade": "1", "annotator": "test"},
    ]

    with session_scope(session_factory) as session:
        validation = validate_imported_labels(session, benchmark, review_rows)

    assert "RQ001:12345678" in validation.duplicate_labels
    assert "99999999" in validation.unknown_pmids


def test_import_annotation_labels_merges_valid_labels(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    _ingest_fixture_corpus(session_factory)

    benchmark_copy = tmp_path / "benchmark.json"
    benchmark_copy.write_text(REAL_BENCHMARK.read_text(encoding="utf-8"), encoding="utf-8")
    review_path = tmp_path / "review.csv"
    review_path.write_text(
        "query_id,pmid,grade,annotator,notes\n"
        "RQ001,12345678,2,reviewer-a,highly relevant fixture paper\n",
        encoding="utf-8",
    )

    with session_scope(session_factory) as session:
        updated, result = import_annotation_labels(
            session,
            benchmark_copy,
            review_path,
        )

    assert result.labels_imported == 1
    assert result.queries_updated == 1
    labeled = [query for query in updated.queries if query.labels]
    assert len(labeled) == 1
    assert labeled[0].labels[0].grade == 2


def test_real_retrieval_benchmark_skips_unlabeled_queries() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    _ingest_fixture_corpus(session_factory)

    benchmark = load_real_benchmark(REAL_BENCHMARK)
    with session_scope(session_factory) as session:
        report = run_real_retrieval_benchmark(session, benchmark)

    assert report.labeled_query_count == 0
    assert report.systems == ()


def test_real_retrieval_benchmark_runs_with_imported_labels(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    _ingest_fixture_corpus(session_factory)

    benchmark_copy = tmp_path / "benchmark_labeled.json"
    benchmark_copy.write_text(REAL_BENCHMARK.read_text(encoding="utf-8"), encoding="utf-8")
    review_path = tmp_path / "review.csv"
    review_path.write_text(
        "query_id,pmid,grade,annotator,notes\n"
        "RQ001,12345678,2,reviewer-a,fixture\n"
        "RQ008,12345678,1,reviewer-a,partial\n",
        encoding="utf-8",
    )

    with session_scope(session_factory) as session:
        import_annotation_labels(session, benchmark_copy, review_path)
        benchmark = load_real_benchmark(benchmark_copy)
        report = run_real_retrieval_benchmark(session, benchmark)

    assert report.labeled_query_count == 2
    system_names = {system.system_name for system in report.systems}
    assert system_names == {
        "bm25",
        "dense_hash",
        "hybrid_hash",
        "hybrid_rerank_lexical",
    }


def test_versioned_corpus_snapshot_manifest_and_checksum(tmp_path: Path) -> None:
    snapshot = load_corpus_snapshot(FIXTURE_CORPUS)
    query_config = PROJECT_ROOT / "data" / "eval" / "domain_corpus_queries.json"
    corpus_path, manifest_path = save_versioned_corpus_snapshot(
        snapshot,
        tmp_path / "rhizonp_domain_v1",
        query_config_path=query_config,
    )
    manifest = verify_corpus_snapshot_directory(corpus_path.parent)
    assert manifest["metadata_only"] is True
    assert manifest["full_text"] is False
    assert manifest_path.exists()
    assert manifest["files"]["corpus.json"]["checksum_sha256"]
