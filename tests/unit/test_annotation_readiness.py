from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import create_engine

from rhizonp.config import PROJECT_ROOT
from rhizonp.domain.models import Base
from rhizonp.evaluation.annotation import (
    BlindAnnotationItem,
    PooledAnnotationCandidate,
    QCAuditMapping,
    SystemHitProvenance,
    apply_qc_duplicates,
    export_pooled_annotation_candidates,
    prepare_blind_annotation_export,
    report_qc_consistency,
    shuffle_blind_items_within_query,
    stable_annotation_item_id,
    write_blind_reviewer_sheet,
)
from rhizonp.evaluation.real_benchmark import load_real_benchmark
from rhizonp.evaluation.retrieval_metrics import judged_at_k
from rhizonp.ingestion.corpus import load_corpus_snapshot, normalized_records_from_snapshot
from rhizonp.ingestion.literature import ingest_literature_records
from rhizonp.storage.postgres import create_session_factory, session_scope

FIXTURE_CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "pubmed" / "corpus_snapshot.json"


def _sample_candidates() -> list[PooledAnnotationCandidate]:
    return [
        PooledAnnotationCandidate(
            query_id="RQ001",
            query_text="q1",
            category="c",
            pmid="100",
            title="t100",
            abstract="a100",
            doi=None,
            source_url=None,
            retrieval_systems=("bm25",),
            provenance_hits=(SystemHitProvenance("bm25", 1, 0.9),),
        ),
        PooledAnnotationCandidate(
            query_id="RQ001",
            query_text="q1",
            category="c",
            pmid="200",
            title="t200",
            abstract="a200",
            doi=None,
            source_url=None,
            retrieval_systems=("dense_hash",),
            provenance_hits=(SystemHitProvenance("dense_hash", 2, 0.8),),
        ),
        PooledAnnotationCandidate(
            query_id="RQ001",
            query_text="q1",
            category="c",
            pmid="300",
            title="t300",
            abstract="a300",
            doi=None,
            source_url=None,
            retrieval_systems=("hybrid_hash",),
            provenance_hits=(SystemHitProvenance("hybrid_hash", 3, 0.7),),
        ),
    ]


def test_stable_annotation_item_id_does_not_encode_rank() -> None:
    item_id = stable_annotation_item_id("RQ001", "12345678")
    assert item_id.startswith("ai_RQ001_")
    assert "rank" not in item_id
    assert stable_annotation_item_id("RQ001", "12345678") == item_id


def test_blind_order_is_deterministic_and_not_pmid_sorted() -> None:
    items = [
        BlindAnnotationItem(
            annotation_item_id=stable_annotation_item_id("RQ001", pmid),
            query_id="RQ001",
            query_text="q1",
            pmid=pmid,
            title=f"t{pmid}",
            abstract=f"a{pmid}",
            doi=None,
        )
        for pmid in ("100", "200", "300", "400", "500")
    ]
    shuffled_a = [item.pmid for item in shuffle_blind_items_within_query(items, shuffle_seed=42)]
    shuffled_b = [item.pmid for item in shuffle_blind_items_within_query(items, shuffle_seed=42)]
    shuffled_other = [item.pmid for item in shuffle_blind_items_within_query(items, shuffle_seed=99)]

    assert shuffled_a == shuffled_b
    assert shuffled_other != shuffled_a
    assert shuffled_a != sorted(shuffled_a) or shuffled_a != ["100", "200", "300", "400", "500"]


def test_prepare_blind_export_assigns_annotation_item_ids() -> None:
    bundle = prepare_blind_annotation_export(_sample_candidates(), shuffle_seed=7)
    assert len(bundle.items) == 3
    assert all(item.annotation_item_id for item in bundle.items)
    assert "rank" not in bundle.items[0].annotation_item_id


def test_qc_duplicates_disabled_by_default() -> None:
    bundle = prepare_blind_annotation_export(_sample_candidates(), qc_fraction=0.0)
    assert bundle.qc_mappings == ()
    assert len(bundle.items) == 3


def test_qc_duplicates_create_private_mapping_when_enabled() -> None:
    primary = [
        BlindAnnotationItem(
            annotation_item_id=stable_annotation_item_id("RQ001", "100"),
            query_id="RQ001",
            query_text="q",
            pmid="100",
            title="t",
            abstract="a",
            doi=None,
        )
    ]
    with_qc, mappings = apply_qc_duplicates(primary, qc_fraction=1.0, qc_seed=1)
    assert len(with_qc) == 2
    assert mappings
    assert mappings[0].qc_annotation_item_id != mappings[0].source_annotation_item_id


def test_qc_consistency_report_exact_and_weighted_agreement() -> None:
    mappings = [
        QCAuditMapping(
            qc_annotation_item_id="qc1",
            source_annotation_item_id="src1",
            query_id="RQ001",
            pmid="100",
        )
    ]
    rows = [
        {"annotation_item_id": "src1", "query_id": "RQ001", "pmid": "100", "grade": "2"},
        {"annotation_item_id": "qc1", "query_id": "RQ001", "pmid": "100", "grade": "1"},
    ]
    report = report_qc_consistency(rows, mappings)
    assert report.pair_count == 1
    assert report.exact_agreement_count == 0
    assert report.weighted_agreement_rate == 0.5


def test_judged_at_k_reports_label_coverage() -> None:
    judged = {"1", "2"}
    retrieved = ["9", "1", "2", "3"]
    assert judged_at_k(judged, retrieved, 5) == 0.5
    assert judged_at_k(judged, retrieved, 2) == 0.5


def test_real_export_blind_sheet_not_rank_ordered(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    records = normalized_records_from_snapshot(load_corpus_snapshot(FIXTURE_CORPUS))
    with session_scope(session_factory) as session:
        ingest_literature_records(session, records)

    benchmark = load_real_benchmark(PROJECT_ROOT / "data" / "eval" / "phase2_real_pubmed_benchmark.json")
    with session_scope(session_factory) as session:
        pooled = export_pooled_annotation_candidates(session, benchmark, pool_depth=5)
    bundle = prepare_blind_annotation_export(pooled, shuffle_seed=123)
    blind_path = write_blind_reviewer_sheet(tmp_path / "blind.csv", bundle)

    with blind_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    rq001_pmids = [row["pmid"] for row in rows if row["query_id"] == "RQ001"]
    if len(rq001_pmids) >= 2:
        assert rq001_pmids != sorted(rq001_pmids)
