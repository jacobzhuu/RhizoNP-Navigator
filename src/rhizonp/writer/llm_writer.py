from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from rhizonp.config import get_settings
from rhizonp.evidence.models import ConstraintValidationContext
from rhizonp.writer.citation_validation import CitationValidationReport, validate_citation_trace
from rhizonp.writer.fallback_writer import write_fallback_answer
from rhizonp.writer.models import AnswerStatus, Claim, GroundedAnswer, WriterRequest

_JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class DeepSeekWriterResult:
    answer: GroundedAnswer
    citation_validation: CitationValidationReport
    constraint_report: Any | None = None
    writer_mode: str = "fallback"
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "answer": self.answer.model_dump(mode="json"),
            "citation_validation": self.citation_validation.to_dict(),
            "writer_mode": self.writer_mode,
            "provider_metadata": dict(self.provider_metadata),
            "issues": list(self.issues),
        }
        if self.constraint_report is not None:
            payload["constraint_validation"] = self.constraint_report.to_dict()
        return payload


def _resolve_api_key() -> tuple[str, str]:
    settings = get_settings()
    if settings.deepseek_api_key:
        return settings.deepseek_api_key, "deepseek"
    if settings.qwen_api_key:
        return settings.qwen_api_key, "qwen"
    return "", ""


def build_bounded_prompt(request: WriterRequest) -> str:
    allowed_ids = [str(item.evidence_id) for item in request.evidence_items]
    evidence_lines: list[str] = []
    for item in request.evidence_items:
        evidence_lines.append(
            json.dumps(
                {
                    "evidence_id": str(item.evidence_id),
                    "claim_type": item.claim_type,
                    "predicate": item.predicate,
                    "object_literal": item.object_literal,
                    "evidence_tier": item.evidence_tier,
                    "directness": item.directness,
                    "supporting_span": item.supporting_span,
                    "warnings": item.warnings,
                },
                ensure_ascii=False,
            )
        )

    return (
        "你是 RhizoNP Navigator 的保守科学证据写作助手。\n"
        "所有面向用户的文本字段（answer、claims[].text、limitations、suggested_validations）"
        "必须使用简体中文。\n"
        "仅返回符合以下 schema 的有效 JSON：\n"
        "{"
        '"status": "SUPPORTED|PARTIALLY_SUPPORTED|INSUFFICIENT_EVIDENCE|CONFLICTING_EVIDENCE", '
        '"answer": "string", '
        '"claims": [{"text": "string", "evidence_refs": ["uuid"], "claim_level": "descriptive|candidate|conflict"}], '
        '"evidence_refs": ["uuid"], '
        '"limitations": ["string"], '
        '"suggested_validations": ["string"]'
        "}\n\n"
        "硬性规则：\n"
        "- 只能使用允许列表中的 evidence ID。\n"
        "- 不得编造 PMID、DOI、source URL 或 evidence ID。\n"
        "- 不得从 MENTIONS 谓词推断生产。\n"
        "- 不得从相关推断因果。\n"
        "- 不得从属级证据主张菌株水平生产。\n"
        "- 不得将 Feature_M123 等未知特征确认为化合物。\n"
        "- 不得将候选证据升级为已确认生产者。\n"
        "- 证据不足时使用 INSUFFICIENT_EVIDENCE 并保守拒答。\n\n"
        f"问题：{request.question}\n"
        f"允许的 evidence ID：{json.dumps(allowed_ids, ensure_ascii=False)}\n"
        f"分类学警告：{json.dumps(request.taxonomy_warnings, ensure_ascii=False)}\n"
        f"限制说明：{json.dumps(request.limitations, ensure_ascii=False)}\n"
        "证据条目：\n"
        + "\n".join(evidence_lines)
    )


def _extract_json_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    block = _JSON_BLOCK_PATTERN.search(text)
    if block:
        text = block.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain a JSON object.")
    return json.loads(text[start : end + 1])


def _normalize_uuid(value: Any) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def parse_llm_structured_answer(
    raw: str,
    request: WriterRequest,
) -> GroundedAnswer:
    payload = _extract_json_payload(raw)
    allowed_ids = {item.evidence_id for item in request.evidence_items}

    status = AnswerStatus(str(payload.get("status")))
    claims: list[Claim] = []
    for claim_payload in payload.get("claims") or []:
        refs = [_normalize_uuid(ref) for ref in claim_payload.get("evidence_refs") or []]
        claims.append(
            Claim(
                text=str(claim_payload.get("text") or ""),
                evidence_refs=refs,
                claim_level=str(claim_payload.get("claim_level") or "descriptive"),
            )
        )

    evidence_refs = [_normalize_uuid(ref) for ref in payload.get("evidence_refs") or []]
    unknown_top_refs = [ref for ref in evidence_refs if ref not in allowed_ids]
    if unknown_top_refs:
        raise ValueError(f"Unknown evidence refs in answer: {unknown_top_refs}")

    return GroundedAnswer(
        status=status,
        answer=str(payload.get("answer") or ""),
        claims=claims,
        evidence_refs=evidence_refs,
        limitations=[str(item) for item in payload.get("limitations") or []],
        suggested_validations=[str(item) for item in payload.get("suggested_validations") or []],
        writer_mode="deepseek_applied",
        provenance={
            "writer": "rhizonp.writer.llm_writer",
            "provider": "deepseek",
            "llm_execution": "remote_structured",
        },
    )


def build_constraint_context(
    request: WriterRequest,
    answer: GroundedAnswer,
    citation_validation: CitationValidationReport,
) -> ConstraintValidationContext:
    return ConstraintValidationContext(
        case_id="DEEPSEEK_WRITER",
        writer_request=request.model_dump(mode="json"),
        grounded_answer=answer.model_dump(mode="json"),
        citation_validation=citation_validation.to_dict(),
        limitations=list(request.limitations),
        taxonomy_grading={
            "warnings": list(request.taxonomy_warnings),
        },
        source_modules=["writer"],
    )


def _fallback_with_mode(
    request: WriterRequest,
    *,
    writer_mode: str,
    issues: list[str],
    provenance: dict[str, Any] | None = None,
) -> DeepSeekWriterResult:
    answer = write_fallback_answer(request)
    merged_provenance = {
        **answer.provenance,
        **(provenance or {}),
        "llm_requested": True,
        "fallback_reason": writer_mode,
    }
    fallback_answer = answer.model_copy(
        update={
            "writer_mode": writer_mode,
            "provenance": merged_provenance,
        }
    )
    validation = validate_citation_trace(request.evidence_items, fallback_answer)
    return DeepSeekWriterResult(
        answer=fallback_answer,
        citation_validation=validation,
        writer_mode=writer_mode,
        issues=issues,
        provider_metadata={"remote_execution": False},
    )


def _default_llm_client(prompt: str) -> str:
    from rhizonp.get_answer import get_llm

    response = get_llm().invoke(prompt)
    content = getattr(response, "content", response)
    return str(content)


def write_deepseek_answer(
    request: WriterRequest,
    *,
    llm_client: Callable[[str], str] | None = None,
    allow_remote: bool = True,
) -> DeepSeekWriterResult:
    api_key, provider = _resolve_api_key()
    settings = get_settings()

    if not api_key:
        answer = write_fallback_answer(request)
        fallback = answer.model_copy(
            update={
                "provenance": {
                    **answer.provenance,
                    "llm_requested": True,
                    "llm_available": False,
                }
            }
        )
        validation = validate_citation_trace(request.evidence_items, fallback)
        return DeepSeekWriterResult(
            answer=fallback,
            citation_validation=validation,
            writer_mode="deterministic_offline",
            provider_metadata={"provider": provider or "deepseek", "api_key_present": False},
            issues=["DEEPSEEK_API_KEY_REQUIRED"],
        )

    if not allow_remote:
        return _fallback_with_mode(
            request,
            writer_mode="deterministic_offline",
            issues=["REMOTE_EXECUTION_DISABLED"],
            provenance={"llm_available": True, "llm_execution": "blocked_by_caller"},
        )

    try:
        invoke = llm_client or _default_llm_client
        raw = invoke(build_bounded_prompt(request))
        answer = parse_llm_structured_answer(raw, request)
        citation_validation = validate_citation_trace(request.evidence_items, answer)
        if citation_validation.dangling_ref_count or citation_validation.unsupported_claim_count:
            return _fallback_with_mode(
                request,
                writer_mode="fallback_after_citation_failure",
                issues=list(citation_validation.issues),
                provenance={
                    "llm_available": True,
                    "llm_execution": "citation_gate_failed",
                },
            )

        from rhizonp.evidence.validator import validate_scientific_constraints

        constraint_report = validate_scientific_constraints(
            build_constraint_context(request, answer, citation_validation)
        )
        if not constraint_report.passed:
            return _fallback_with_mode(
                request,
                writer_mode="fallback_after_constraint_violation",
                issues=list(constraint_report.issues),
                provenance={
                    "llm_available": True,
                    "llm_execution": "constraint_gate_failed",
                },
            )

        return DeepSeekWriterResult(
            answer=answer,
            citation_validation=citation_validation,
            constraint_report=constraint_report,
            writer_mode="deepseek_applied",
            provider_metadata={
                "provider": provider,
                "model": settings.llm_model,
                "base_url": settings.llm_api_base,
                "api_key_present": True,
                "remote_execution": True,
            },
        )
    except json.JSONDecodeError as exc:
        return _fallback_with_mode(
            request,
            writer_mode="fallback_after_schema_failure",
            issues=[f"Malformed JSON: {exc}"],
            provenance={"llm_available": True, "llm_execution": "schema_parse_failed"},
        )
    except ValueError as exc:
        return _fallback_with_mode(
            request,
            writer_mode="fallback_after_schema_failure",
            issues=[str(exc)],
            provenance={"llm_available": True, "llm_execution": "schema_validation_failed"},
        )
    except Exception as exc:  # pragma: no cover - exercised via timeout/failure tests
        return _fallback_with_mode(
            request,
            writer_mode="fallback_after_provider_error",
            issues=[f"{type(exc).__name__}: {exc}"],
            provenance={"llm_available": True, "llm_execution": "provider_error"},
        )


def check_llm_configuration() -> dict[str, Any]:
    settings = get_settings()
    api_key, provider = _resolve_api_key()
    provider_configured = provider in {"deepseek", "qwen"}
    return {
        "provider_configured": provider_configured,
        "provider": provider or "deepseek",
        "api_key_present": bool(api_key),
        "base_url_configured": bool(settings.llm_api_base),
        "model_configured": bool(settings.llm_model),
        "live_evaluation_ready": bool(api_key and settings.llm_api_base and settings.llm_model),
        "status": "READY_FOR_USER_CONFIGURATION" if not api_key else "LIVE_EVALUATION_READY",
    }
