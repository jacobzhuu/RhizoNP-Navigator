from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from rhizonp.domain.models import Base
from rhizonp.ingestion.literature import load_phase2_literature_fixture
from rhizonp.query.assistant import build_question_plan, run_ask_pipeline
from rhizonp.storage.postgres import create_session_factory
from rhizonp.writer.models import AnswerStatus


def test_build_question_plan_expands_domain_terms_and_preserves_claim_boundaries() -> None:
    plan = build_question_plan(
        "检测到 Streptomyces 是否说明样本中存在天然产物生产证据？"
    )

    assert plan.intent == "must_bound_claim"
    assert plan.entities["taxa"] == ["Streptomyces"]
    assert "natural product" in plan.synonym_expansions
    assert "secondary metabolite" in plan.synonym_expansions["natural product"]
    assert any(query.query_type == "taxon_np_expansion" for query in plan.planned_queries)
    assert any("较强结论" in warning for warning in plan.warnings)
    assert plan.planner_mode == "deterministic_domain_rules"


def test_real_npatlas_question_produces_supported_answer() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session = create_session_factory(engine)()
    try:
        load_phase2_literature_fixture(session)
        session.commit()
        result = run_ask_pipeline(
            session,
            "Streptomyces sp. SANK 62799 是否有 A-503083 F 生产记录？",
            retrieval_mode="bm25",
            use_llm=False,
        )
    finally:
        session.close()

    assert result.question_plan.entities["taxa"] == ["Streptomyces sp. SANK 62799"]
    assert result.writer_result.answer.status == AnswerStatus.SUPPORTED
    assert result.writer_result.evidence_items[0].predicate == "PRODUCES"
    assert result.writer_result.evidence_items[0].provenance["source_database"] == "npatlas"
    assert result.writer_result.evidence_items[0].provenance["not_synthetic_fixture"] is True
    assert "fixture" not in " ".join(result.writer_result.answer.limitations).lower()
