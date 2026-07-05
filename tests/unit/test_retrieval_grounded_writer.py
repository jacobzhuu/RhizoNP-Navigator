from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from rhizonp.domain.models import Base
from rhizonp.ingestion.literature import load_phase2_literature_fixture
from rhizonp.omics.pipeline import OwnDataPipelineOptions, run_own_data_pipeline
from rhizonp.storage.postgres import create_session_factory
from rhizonp.writer.citation_validation import validate_citation_trace
from rhizonp.writer.evidence_adapter import (
    literature_hit_to_evidence_item,
    stable_evidence_id_for_chunk,
)
from rhizonp.writer.fallback_writer import write_fallback_answer
from rhizonp.writer.models import AnswerStatus, EvidenceInput, WriterRequest
from rhizonp.writer.retrieval_writer import (
    build_writer_request_from_literature_hits,
    write_grounded_answer_from_literature_hits,
)


def _literature_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    load_phase2_literature_fixture(session)
    session.commit()
    return session


def _sample_hit(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "query_text": "Streptomyces Rapamycin",
        "query_index": 1,
        "paper_id": "paper-1",
        "chunk_id": "chunk-1",
        "title": "Fixture paper on Streptomyces metabolites",
        "supporting_text": "Streptomyces strains can produce rapamycin-like metabolites in soil.",
        "pmid": "12345678",
        "doi": "10.1000/fixture.1",
        "source_url": "https://example.org/fixture/1",
        "journal": "Fixture Journal",
        "year": 2024,
        "section": "abstract",
        "retrieval_mode": "bm25",
        "retrieval_score": 0.91,
        "matched_terms": ["Streptomyces", "rapamycin"],
        "provenance": {"corpus_type": "FIXTURE_TEST_ONLY", "trace": {"chunk_id": "chunk-1"}},
        "source_type": "paper",
        "is_fixture": True,
        "taxonomy_grading": {
            "status": "graded",
            "grading": {
                "evidence_tier": "C",
                "taxonomy_distance": "SAME_GENUS",
                "warnings": ["Genus-level observation cannot support strain-level production claims."],
            },
        },
    }
    payload.update(overrides)
    return payload


def test_literature_hit_to_evidence_item_preserves_pmid_and_trace() -> None:
    item = literature_hit_to_evidence_item(_sample_hit())
    assert item.provenance["pmid"] == "12345678"
    assert item.provenance["chunk_id"] == "chunk-1"
    assert item.provenance["paper_id"] == "paper-1"
    assert item.predicate == "MENTIONS"
    assert item.claim_type == "literature_retrieval_clue"
    assert item.evidence_id == stable_evidence_id_for_chunk("chunk-1")


def test_writer_from_literature_hits_produces_valid_citations() -> None:
    result = write_grounded_answer_from_literature_hits(
        "What literature mentions Streptomyces metabolites?",
        [_sample_hit()],
    )
    assert result.answer.claims
    assert result.citation_validation.citation_ref_validity_rate == 1.0
    assert result.citation_validation.evidence_trace_completeness == 1.0
    assert result.faithfulness_diagnostics
    assert result.faithfulness_diagnostics[0]["human_faithfulness_pending"] is True


def test_dangling_ref_detected() -> None:
    evidence = literature_hit_to_evidence_item(_sample_hit())
    answer = write_fallback_answer(
        WriterRequest(
            question="Test",
            evidence_items=[evidence],
        )
    )
    broken = answer.model_copy(
        update={
            "claims": [
                answer.claims[0].model_copy(
                    update={"evidence_refs": [uuid.uuid4()]},
                )
            ]
        }
    )
    report = validate_citation_trace([evidence], broken)
    assert report.dangling_ref_count >= 1


def test_insufficient_evidence_when_no_hits() -> None:
    result = write_grounded_answer_from_literature_hits(
        "Any evidence?",
        [],
    )
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE


def test_fixture_provenance_warning_present() -> None:
    request = build_writer_request_from_literature_hits(
        "Question?",
        [_sample_hit()],
    )
    assert any("fixture" in warning.lower() for warning in request.taxonomy_warnings)


@pytest.mark.skipif(
    not (__import__("pathlib").Path(__file__).resolve().parents[2] / "data" / "fixtures" / "own_data_demo").is_dir(),
    reason="own-data demo fixture missing",
)
def test_own_data_pipeline_opt_in_grounded_writer() -> None:
    from rhizonp.config import PROJECT_ROOT

    session = _literature_session()
    try:
        result = run_own_data_pipeline(
            PROJECT_ROOT / "data" / "fixtures" / "own_data_demo",
            session=session,
            options=OwnDataPipelineOptions(
                enable_literature_retrieval=True,
                enable_grounded_writer=True,
            ),
        )
    finally:
        session.close()
    first = result.association_results[0]
    assert first.grounded_writer is not None
    assert first.grounded_writer["answer"]["status"] in {
        "PARTIALLY_SUPPORTED",
        "INSUFFICIENT_EVIDENCE",
        "SUPPORTED",
        "CONFLICTING_EVIDENCE",
    }


def test_conflict_status_from_explicit_predicates() -> None:
    support = EvidenceInput(
        evidence_id=uuid.uuid4(),
        claim_type="taxon_produces_compound",
        predicate="PRODUCES",
        object_literal="Rapamycin",
        evidence_tier="B",
    )
    conflict = EvidenceInput(
        evidence_id=uuid.uuid4(),
        claim_type="taxon_produces_compound",
        predicate="DOES_NOT_PRODUCE",
        object_literal="Rapamycin",
        evidence_tier="B",
    )
    answer = write_fallback_answer(
        WriterRequest(
            question="Does the taxon produce rapamycin?",
            evidence_items=[support, conflict],
        )
    )
    assert answer.status == AnswerStatus.CONFLICTING_EVIDENCE
