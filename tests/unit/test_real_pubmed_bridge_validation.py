from __future__ import annotations

from pathlib import Path

from rhizonp.omics.corpus_provenance import CorpusType, classify_paper, classify_record_entry
from rhizonp.omics.real_pubmed_validation import (
    ingest_bounded_pubmed_snapshot,
    run_real_pubmed_validation,
    write_validation_reports,
)

FIXTURE_SAMPLE = Path(__file__).resolve().parents[1] / "fixtures" / "pubmed" / "real_bounded_sample.json"
PHASE2_FIXTURE = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "phase2_literature_demo.json"


def test_classify_real_pubmed_record_entry() -> None:
    import json

    payload = json.loads(FIXTURE_SAMPLE.read_text(encoding="utf-8"))
    real_record = payload["records"][0]
    fixture_record = payload["records"][1]
    assert classify_record_entry(real_record) == CorpusType.REAL_BOUNDED_PUBMED
    assert classify_record_entry(fixture_record) == CorpusType.FIXTURE_TEST_ONLY


def test_classify_phase2_synthetic_paper_as_fixture() -> None:
    import json

    from rhizonp.domain.models import Paper

    payload = json.loads(PHASE2_FIXTURE.read_text(encoding="utf-8"))
    record = payload["records"][0]
    paper = Paper(
        title=record["title"],
        doi=record["doi"],
        source_url=record["source_url"],
        provenance={"fixture": True, "not_real_literature": True},
        journal=record.get("journal"),
    )
    assert classify_paper(paper) == CorpusType.FIXTURE_TEST_ONLY


def test_real_bounded_sample_ingest_and_bridge_validation(tmp_path: Path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from rhizonp.domain.models import Base
    from rhizonp.omics.real_pubmed_validation import (
        run_direct_retrieval_validation,
        run_own_data_bridge_validation,
    )
    from rhizonp.storage.postgres import create_session_factory

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session: Session = session_factory()
    try:
        ingest_summary, corpus_type, corpus_id = ingest_bounded_pubmed_snapshot(
            session,
            FIXTURE_SAMPLE,
            verify_manifest=False,
        )
        assert corpus_type == CorpusType.REAL_BOUNDED_PUBMED
        assert ingest_summary.pmid_coverage >= 0.5
        assert ingest_summary.paper_count >= 1

        direct = run_direct_retrieval_validation(
            session,
            corpus_id=corpus_id,
            corpus_type=corpus_type.value,
            queries=("Streptomyces rhizosphere secondary metabolites",),
            top_k=2,
        )
        assert direct[0]["hit_count"] >= 1
        assert direct[0]["hits"][0]["is_real_pubmed"] is True
        assert direct[0]["hits"][0]["pmid"] == "42348782"

        bridge = run_own_data_bridge_validation(
            session,
            corpus_id=corpus_id,
            corpus_type=corpus_type.value,
            top_k=2,
        )
        feature = next(row for row in bridge if row["target_raw_label"] == "Feature_M123")
        assert "Feature_M123" not in " ".join(
            item["query_text"] for item in feature["generated_queries"]
        )
        assert feature["top_hit"] is not None
        assert feature["top_hit"]["pmid"] == "42348782"
        assert feature["corpus_type"] == CorpusType.REAL_BOUNDED_PUBMED.value
        assert feature["literature_status"] == "RETRIEVED"
    finally:
        session.close()


def test_real_pubmed_validation_report_writes_files(tmp_path: Path) -> None:
    report = run_real_pubmed_validation(
        snapshot_path=FIXTURE_SAMPLE,
        retrieval_mode="bm25",
        top_k=2,
    )
    json_path, md_path = write_validation_reports(report, tmp_path)
    assert json_path.exists()
    assert md_path.exists()
    assert report.real_trace_present is True
    assert report.real_trace is not None
    assert report.real_trace["pmid"] == "42348782"


def test_fixture_corpus_stays_fixture_test_only() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from rhizonp.domain.models import Base
    from rhizonp.ingestion.literature import load_phase2_literature_fixture
    from rhizonp.omics.pipeline import OwnDataPipelineOptions, run_own_data_pipeline
    from rhizonp.storage.postgres import create_session_factory

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session: Session = session_factory()
    try:
        load_phase2_literature_fixture(session)
        session.commit()
        result = run_own_data_pipeline(
            session=session,
            options=OwnDataPipelineOptions(
                enable_literature_retrieval=True,
                retrieval_mode="bm25",
                corpus_id="phase2_fixture",
                corpus_type=CorpusType.FIXTURE_TEST_ONLY.value,
            ),
        )
        literature = result.association_results[0].literature_retrieval
        assert literature["status"] == "FIXTURE_TEST_ONLY"
        assert literature["provenance"]["corpus_type"] == CorpusType.FIXTURE_TEST_ONLY.value
    finally:
        session.close()
