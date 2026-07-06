from __future__ import annotations

from rhizonp.writer.models import AnswerStatus, GroundedAnswer


def derive_answer_mode(answer: GroundedAnswer) -> str:
    mode = answer.writer_mode
    if mode in {"deterministic_offline", "fallback", "fallback_after_citation_failure",
                "fallback_after_constraint_violation", "fallback_after_schema_failure",
                "fallback_after_provider_error"}:
        return "deterministic_fallback"
    if mode == "llm_constraint_repaired":
        return "llm_constraint_repaired"
    if mode == "llm_partial_grounding":
        return "llm_partial_grounding"
    if mode in {"llm_general_knowledge", "deepseek_general_knowledge"}:
        return "llm_general_knowledge"
    if mode in {"llm_grounded", "deepseek_applied"}:
        return "llm_grounded"
    if answer.claims and answer.evidence_refs:
        return "llm_grounded"
    if answer.answer and not answer.evidence_refs:
        return "llm_general_knowledge"
    return "deterministic_fallback"


def derive_evidence_status(status: AnswerStatus | str) -> str:
    normalized = status.value if isinstance(status, AnswerStatus) else str(status)
    mapping = {
        AnswerStatus.SUPPORTED.value: "sufficient",
        AnswerStatus.PARTIALLY_SUPPORTED.value: "partial",
        AnswerStatus.INSUFFICIENT_EVIDENCE.value: "none",
        AnswerStatus.CONFLICTING_EVIDENCE.value: "conflicting",
    }
    return mapping.get(normalized, "none")


def derive_llm_status(answer: GroundedAnswer, *, llm_requested: bool) -> str:
    if not llm_requested:
        return "not_requested"
    provenance = answer.provenance or {}
    if provenance.get("llm_available") is False:
        return "unavailable"
    mode = answer.writer_mode
    if mode == "llm_constraint_repaired":
        return "repaired"
    if mode.startswith("fallback"):
        return "failed"
    if mode in {"deterministic_offline", "fallback"}:
        return "failed" if llm_requested else "not_requested"
    if mode.startswith("llm_") or mode.startswith("deepseek_"):
        return "applied"
    return "failed"


def enrich_grounded_answer_metadata(answer: GroundedAnswer, *, llm_requested: bool) -> dict[str, str]:
    return {
        "answer_mode": derive_answer_mode(answer),
        "evidence_status": derive_evidence_status(answer.status),
        "llm_status": derive_llm_status(answer, llm_requested=llm_requested),
    }
