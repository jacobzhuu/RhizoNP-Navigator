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
        "你是 RhizoNP Navigator 的科学问答助手。你需要始终利用通用科学知识给出有信息量的回答；"
        "本地知识库/检索证据如果存在，则作为额外上下文和可追溯引用使用。\n"
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
        "- status 只表示本地证据支持度，不表示你是否可以回答："
        "本地证据强则 SUPPORTED，候选/间接证据则 PARTIALLY_SUPPORTED，"
        "没有可用本地证据则 INSUFFICIENT_EVIDENCE，证据互相冲突则 CONFLICTING_EVIDENCE。\n"
        "- answer 必须正常回答问题，可以使用通用科学知识；但必须清楚区分“本地证据支持的内容”"
        "和“通用知识/推理性补充”。\n"
        "- claims[] 只能写本地证据直接支持的主张；每条 claims[] 必须至少包含一个允许列表中的 evidence_refs。"
        "没有本地证据引用的通用知识不要放进 claims[]。\n"
        "- 顶层 evidence_refs 必须等于所有 claims[].evidence_refs 的去重并集；"
        "没有可引用本地证据时 claims=[] 且 evidence_refs=[]。\n"
        "- 不得编造 PMID、DOI、source URL 或 evidence ID。\n"
        "- 不得把数据库描述为人工审核、权威、可靠或已实验验证，除非证据字段明确提供这些信息。\n"
        "- 不得从 MENTIONS 谓词推断生产。\n"
        "- 不得从相关推断因果。\n"
        "- 不得从属级证据主张菌株水平生产。\n"
        "- 不得将 Feature_M123 等未知特征确认为化合物。\n"
        "- 不得将候选证据升级为已确认生产者。\n"
        "- 当证据谓词为 PRODUCES、evidence_tier=A 且 directness=direct 时，可以输出 SUPPORTED；"
        "若该证据来自 fixture/test 语料，必须说明它只支持演示数据范围内的结论。\n"
        "- 不要让 D 级 MENTIONS 背景片段覆盖 A 级直接证据；"
        "弱证据可作为局限或背景，但不能削弱已引用的直接证据。\n"
        "- 本地证据不足时使用 INSUFFICIENT_EVIDENCE，但不要空泛拒答；"
        "应先说明本地知识库未找到可引用证据，再给出通用知识层面的谨慎回答。\n\n"
        "写作要求：answer 字段写成 2-4 个简短段落，而不是一句状态说明。"
        "需要覆盖：直接回答、通用知识背景、本地证据是否支持以及支持到什么程度、"
        "证据等级/分类学边界、fixture/test 语料或检索线索的局限、下一步验证方向。"
        "claims[].text 保持简洁，每条主张只写一个可由 evidence_refs 支撑的事实。"
        "不要在 answer 文本中列出 evidence_id；引用绑定由 evidence_refs 字段完成。"
        "避免堆叠工程术语，避免输出英文限制语。\n\n"
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
    has_local_evidence = bool(request.evidence_items)

    status = AnswerStatus(str(payload.get("status")))
    if not has_local_evidence:
        status = AnswerStatus.INSUFFICIENT_EVIDENCE

    claims: list[Claim] = []
    for claim_payload in (payload.get("claims") or []) if has_local_evidence else []:
        refs = [_normalize_uuid(ref) for ref in claim_payload.get("evidence_refs") or []]
        claims.append(
            Claim(
                text=str(claim_payload.get("text") or ""),
                evidence_refs=refs,
                claim_level=str(claim_payload.get("claim_level") or "descriptive"),
            )
        )

    evidence_refs = (
        [_normalize_uuid(ref) for ref in payload.get("evidence_refs") or []]
        if has_local_evidence
        else []
    )
    unknown_top_refs = [ref for ref in evidence_refs if ref not in allowed_ids]
    if unknown_top_refs:
        raise ValueError(f"Unknown evidence refs in answer: {unknown_top_refs}")

    limitations = [str(item) for item in payload.get("limitations") or []]
    if not has_local_evidence:
        limitations = [
            "本地知识库未检索到可引用证据；以下回答来自大模型通用知识，不能作为本系统证据支持。",
            *limitations,
        ]

    return GroundedAnswer(
        status=status,
        answer=str(payload.get("answer") or ""),
        claims=claims,
        evidence_refs=evidence_refs,
        limitations=limitations,
        suggested_validations=[str(item) for item in payload.get("suggested_validations") or []],
        writer_mode="llm_grounded" if has_local_evidence else "llm_general_knowledge",
        provenance={
            "writer": "rhizonp.writer.llm_writer",
            "provider": "deepseek",
            "llm_execution": (
                "remote_general_knowledge_with_evidence_context"
                if has_local_evidence
                else "remote_general_knowledge_after_kb_miss"
            ),
            "local_evidence_count": len(request.evidence_items),
        },
    )


def build_general_knowledge_prompt(request: WriterRequest) -> str:
    return (
        "你是 RhizoNP Navigator 的科学问答助手。当前没有可加入上下文的本地证据条目，"
        "但你仍然需要基于通用科学知识回答用户问题。\n"
        "所有面向用户的文本字段必须使用简体中文。\n"
        "只返回一个 JSON 对象，不要输出 Markdown，不要输出 JSON 之外的解释文字。\n"
        "JSON schema：\n"
        "{"
        '"status": "INSUFFICIENT_EVIDENCE", '
        '"answer": "string", '
        '"claims": [], '
        '"evidence_refs": [], '
        '"limitations": ["string"], '
        '"suggested_validations": ["string"]'
        "}\n\n"
        "硬性规则：\n"
        "- status 必须是 INSUFFICIENT_EVIDENCE，表示本地知识库没有证据支撑。\n"
        "- claims 必须是空数组，evidence_refs 必须是空数组。\n"
        "- answer 第一段必须明确说明：本地知识库未检索到可引用证据，以下是通用知识回答。\n"
        "- 可以使用通用科学知识解释背景、常见机制、合理判断和验证路径。\n"
        "- 不得编造 PMID、DOI、论文标题、source URL 或本地 evidence ID。\n"
        "- 不要声称这是 RhizoNP 知识库支持的结论。\n"
        "- 对具体菌株、具体化合物生产能力、因果关系或实验结果必须保守。\n"
        "- answer 写成 2-4 个简短段落，避免只给一句话。\n\n"
        f"问题：{request.question}\n"
        f"本地限制说明：{json.dumps(request.limitations, ensure_ascii=False)}\n"
    )


def parse_general_knowledge_answer(raw: str, request: WriterRequest) -> GroundedAnswer:
    return parse_llm_structured_answer(raw, request)


def _unstructured_general_knowledge_answer(
    raw: str,
    request: WriterRequest,
    *,
    issue: str,
) -> GroundedAnswer:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*```$", "", text).strip()
    if not text:
        text = "模型未返回可用文本。"
    answer_text = (
        "本地知识库未检索到可引用证据，以下是通用知识回答。\n\n"
        f"{text[:4000]}"
    )
    return GroundedAnswer(
        status=AnswerStatus.INSUFFICIENT_EVIDENCE,
        answer=answer_text,
        claims=[],
        evidence_refs=[],
        limitations=[
            "本地知识库未检索到可引用证据；以下回答来自大模型通用知识，不能作为本系统证据支持。",
            "模型返回未通过结构化 JSON 校验，系统仅保留其非引用性通用回答文本。",
            *list(request.limitations),
        ],
        suggested_validations=[
            "补充本地文献、数据库记录或实验数据后重新提问。",
        ],
        writer_mode="llm_general_knowledge",
        provenance={
            "writer": "rhizonp.writer.llm_writer",
            "provider": "deepseek",
            "llm_execution": "remote_general_knowledge_unstructured_after_schema_failure",
            "local_evidence_count": len(request.evidence_items),
            "schema_issue": issue,
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


def _soft_degrade_citation_failure(
    answer: GroundedAnswer,
    request: WriterRequest,
    validation: CitationValidationReport,
) -> GroundedAnswer:
    limitations = list(answer.limitations)
    limitations.insert(
        0,
        "部分主张未能绑定到本地证据引用，以下回答以通用知识为主。",
    )
    for issue in validation.issues:
        limitations.append(str(issue))
    return answer.model_copy(
        update={
            "claims": [],
            "evidence_refs": [],
            "status": AnswerStatus.INSUFFICIENT_EVIDENCE,
            "limitations": list(dict.fromkeys(limitations)),
            "writer_mode": "llm_partial_grounding",
            "provenance": {
                **answer.provenance,
                "llm_execution": "citation_soft_degrade",
            },
        }
    )


def build_constraint_rewrite_prompt(
    request: WriterRequest,
    *,
    violations: list[str],
) -> str:
    return (
        "你是 RhizoNP Navigator 的科学问答助手。先前回答违反了科学边界，需要重写。\n"
        "仅返回 JSON，schema 与先前相同（status, answer, claims, evidence_refs, limitations, "
        "suggested_validations）。\n"
        "硬性规则：\n"
        "- 删除或弱化所有违规主张；不得保留过度确定性、因果越界或菌株级结论。\n"
        "- claims 只能引用允许的 evidence ID；无法安全引用时 claims=[]。\n"
        "- answer 仍须回答问题，但使用谨慎的通用知识表述。\n"
        "- 所有用户可见文本使用简体中文。\n\n"
        f"违规项：{json.dumps(violations, ensure_ascii=False)}\n"
        f"问题：{request.question}\n"
        f"分类学警告：{json.dumps(request.taxonomy_warnings, ensure_ascii=False)}\n"
        f"限制说明：{json.dumps(request.limitations, ensure_ascii=False)}\n"
    )


def _safe_fallback_after_constraint_failure(
    request: WriterRequest,
    issues: list[str],
) -> DeepSeekWriterResult:
    answer = write_fallback_answer(request)
    fallback = answer.model_copy(
        update={
            "writer_mode": "deterministic_fallback",
            "limitations": [
                "大模型回答未通过科学约束校验，已回退到规则化安全回答。",
                *list(request.limitations),
                *issues,
            ],
            "provenance": {
                **answer.provenance,
                "llm_requested": True,
                "llm_execution": "constraint_safe_fallback",
            },
        }
    )
    validation = validate_citation_trace(request.evidence_items, fallback)
    return DeepSeekWriterResult(
        answer=fallback,
        citation_validation=validation,
        writer_mode="deterministic_fallback",
        issues=issues,
        provider_metadata={"remote_execution": True, "grounding": "constraint_safe_fallback"},
    )


def _finalize_llm_result(
    request: WriterRequest,
    answer: GroundedAnswer,
    *,
    provider: str,
    settings: Any,
    constraint_report: Any | None = None,
) -> DeepSeekWriterResult:
    citation_validation = validate_citation_trace(request.evidence_items, answer)
    return DeepSeekWriterResult(
        answer=answer,
        citation_validation=citation_validation,
        constraint_report=constraint_report,
        writer_mode=answer.writer_mode,
        provider_metadata={
            "provider": provider,
            "model": settings.llm_model,
            "base_url": settings.llm_api_base,
            "api_key_present": True,
            "remote_execution": True,
            "grounding": (
                "general_knowledge_with_local_evidence_context"
                if request.evidence_items
                else "general_knowledge_after_local_kb_miss"
            ),
        },
    )


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

    raw: str | None = None
    try:
        invoke = llm_client or _default_llm_client
        prompt = build_bounded_prompt(request) if request.evidence_items else build_general_knowledge_prompt(request)
        raw = invoke(prompt)
        answer = parse_llm_structured_answer(raw, request)
        citation_validation = validate_citation_trace(request.evidence_items, answer)
        if citation_validation.dangling_ref_count or citation_validation.unsupported_claim_count:
            answer = _soft_degrade_citation_failure(answer, request, citation_validation)
            citation_validation = validate_citation_trace(request.evidence_items, answer)

        from rhizonp.evidence.validator import validate_scientific_constraints

        constraint_report = validate_scientific_constraints(
            build_constraint_context(request, answer, citation_validation)
        )
        if not constraint_report.passed:
            rewrite_prompt = build_constraint_rewrite_prompt(
                request,
                violations=list(constraint_report.issues),
            )
            rewritten_raw = invoke(rewrite_prompt)
            try:
                rewritten_answer = parse_llm_structured_answer(rewritten_raw, request)
                rewritten_answer = rewritten_answer.model_copy(
                    update={
                        "writer_mode": "llm_constraint_repaired",
                        "provenance": {
                            **rewritten_answer.provenance,
                            "llm_execution": "constraint_repaired",
                        },
                    }
                )
                rewritten_validation = validate_citation_trace(request.evidence_items, rewritten_answer)
                if rewritten_validation.dangling_ref_count or rewritten_validation.unsupported_claim_count:
                    rewritten_answer = _soft_degrade_citation_failure(
                        rewritten_answer,
                        request,
                        rewritten_validation,
                    )
                    rewritten_validation = validate_citation_trace(request.evidence_items, rewritten_answer)
                rewritten_constraints = validate_scientific_constraints(
                    build_constraint_context(request, rewritten_answer, rewritten_validation)
                )
                if rewritten_constraints.passed:
                    return _finalize_llm_result(
                        request,
                        rewritten_answer,
                        provider=provider,
                        settings=settings,
                        constraint_report=rewritten_constraints,
                    )
            except (json.JSONDecodeError, ValueError):
                pass
            return _safe_fallback_after_constraint_failure(
                request,
                list(constraint_report.issues),
            )

        return _finalize_llm_result(
            request,
            answer,
            provider=provider,
            settings=settings,
            constraint_report=constraint_report,
        )
    except json.JSONDecodeError as exc:
        if not request.evidence_items and raw:
            answer = _unstructured_general_knowledge_answer(raw, request, issue=f"Malformed JSON: {exc}")
            return DeepSeekWriterResult(
                answer=answer,
                citation_validation=validate_citation_trace(request.evidence_items, answer),
                writer_mode=answer.writer_mode,
                provider_metadata={"remote_execution": True, "grounding": "general_knowledge_after_local_kb_miss"},
                issues=[f"Malformed JSON: {exc}"],
            )
        return _fallback_with_mode(
            request,
            writer_mode="fallback_after_schema_failure",
            issues=[f"Malformed JSON: {exc}"],
            provenance={"llm_available": True, "llm_execution": "schema_parse_failed"},
        )
    except ValueError as exc:
        if not request.evidence_items and raw:
            answer = _unstructured_general_knowledge_answer(raw, request, issue=str(exc))
            return DeepSeekWriterResult(
                answer=answer,
                citation_validation=validate_citation_trace(request.evidence_items, answer),
                writer_mode=answer.writer_mode,
                provider_metadata={"remote_execution": True, "grounding": "general_knowledge_after_local_kb_miss"},
                issues=[str(exc)],
            )
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
