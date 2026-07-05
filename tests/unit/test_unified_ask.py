from __future__ import annotations

from rhizonp.query.assistant import build_question_plan


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
