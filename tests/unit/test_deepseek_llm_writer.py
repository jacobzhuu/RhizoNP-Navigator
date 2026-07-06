from __future__ import annotations

import json
import uuid

import pytest

from rhizonp.config import get_settings
from rhizonp.writer.llm_writer import (
    build_bounded_prompt,
    check_llm_configuration,
    parse_llm_structured_answer,
    write_deepseek_answer,
)
from rhizonp.writer.models import AnswerStatus, EvidenceInput, WriterRequest
from rhizonp.writer.service import write_grounded_answer, write_llm_answer


def _request(**overrides: object) -> WriterRequest:
    evidence_id = uuid.uuid4()
    payload = {
        "question": "What is supported?",
        "evidence_items": [
            EvidenceInput(
                evidence_id=evidence_id,
                claim_type="association",
                predicate="MENTIONS",
                object_literal="Feature_M123",
                evidence_tier="C",
                supporting_span="Genus-level mention only.",
                warnings=["Feature_M123 is not structure-confirmed."],
                provenance={"pmid": "42348782", "chunk_id": "chunk-1", "paper_id": "paper-1"},
            )
        ],
        "taxonomy_warnings": ["Genus-level observation cannot support strain-level production claims."],
        "limitations": ["Correlation is not causation."],
    }
    payload.update(overrides)
    return WriterRequest.model_validate(payload)


def test_check_llm_configuration_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("QWEN_API_KEY", "")
    get_settings.cache_clear()
    report = check_llm_configuration()
    assert report["api_key_present"] is False
    assert report["live_evaluation_ready"] is False
    assert report["status"] == "READY_FOR_USER_CONFIGURATION"


def test_write_deepseek_answer_without_api_key_uses_offline_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("QWEN_API_KEY", "")
    get_settings.cache_clear()
    result = write_deepseek_answer(_request())
    assert result.writer_mode == "deterministic_offline"
    assert "DEEPSEEK_API_KEY_REQUIRED" in result.issues
    assert result.answer.writer_mode == "fallback"


def test_valid_structured_deepseek_style_response() -> None:
    request = _request()
    evidence_id = request.evidence_items[0].evidence_id
    raw = json.dumps(
        {
            "status": "PARTIALLY_SUPPORTED",
            "answer": "Only genus-level mention evidence is available.",
            "claims": [
                {
                    "text": "Literature mentions Streptomyces in a metabolite context.",
                    "evidence_refs": [str(evidence_id)],
                    "claim_level": "candidate",
                }
            ],
            "evidence_refs": [str(evidence_id)],
            "limitations": ["Correlation is not causation."],
            "suggested_validations": ["Confirm metabolite identity."],
        }
    )
    answer = parse_llm_structured_answer(raw, request)
    assert answer.status == AnswerStatus.PARTIALLY_SUPPORTED
    assert answer.claims[0].evidence_refs == [evidence_id]


def test_malformed_json_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-placeholder")
    get_settings.cache_clear()
    request = _request()

    def bad_client(_prompt: str) -> str:
        return "not json"

    result = write_deepseek_answer(request, llm_client=bad_client, allow_remote=True)
    assert result.writer_mode == "fallback_after_schema_failure"


def test_schema_failure_unknown_evidence_ref() -> None:
    request = _request()
    raw = json.dumps(
        {
            "status": "SUPPORTED",
            "answer": "unsupported",
            "claims": [],
            "evidence_refs": [str(uuid.uuid4())],
            "limitations": [],
            "suggested_validations": [],
        }
    )
    with pytest.raises(ValueError, match="Unknown evidence refs"):
        parse_llm_structured_answer(raw, request)


def test_dangling_citation_ref_triggers_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-placeholder")
    get_settings.cache_clear()
    request = _request()
    evidence_id = request.evidence_items[0].evidence_id
    dangling_id = uuid.uuid4()

    def client(_prompt: str) -> str:
        return json.dumps(
            {
                "status": "SUPPORTED",
                "answer": "bad refs",
                "claims": [{"text": "bad", "evidence_refs": [str(dangling_id)], "claim_level": "descriptive"}],
                "evidence_refs": [str(evidence_id)],
                "limitations": [],
                "suggested_validations": [],
            }
        )

    result = write_deepseek_answer(request, llm_client=client, allow_remote=True)
    assert result.writer_mode == "llm_partial_grounding"
    assert result.answer.claims == []


def test_taxonomy_overclaim_triggers_constraint_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-placeholder")
    get_settings.cache_clear()
    request = _request()
    evidence_id = request.evidence_items[0].evidence_id

    def client(_prompt: str) -> str:
        return json.dumps(
            {
                "status": "SUPPORTED",
                "answer": "This sample produces Feature_M123 at strain level.",
                "claims": [
                    {
                        "text": "Strain-level production is confirmed for Feature_M123.",
                        "evidence_refs": [str(evidence_id)],
                        "claim_level": "descriptive",
                    }
                ],
                "evidence_refs": [str(evidence_id)],
                "limitations": [],
                "suggested_validations": [],
            }
        )

    result = write_deepseek_answer(request, llm_client=client, allow_remote=True)
    assert result.writer_mode == "deterministic_fallback"


def test_provider_failure_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-placeholder")
    get_settings.cache_clear()
    request = _request()

    def failing_client(_prompt: str) -> str:
        raise TimeoutError("provider timeout")

    result = write_deepseek_answer(request, llm_client=failing_client, allow_remote=True)
    assert result.writer_mode == "fallback_after_provider_error"


def test_empty_evidence_uses_general_knowledge_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-placeholder")
    get_settings.cache_clear()
    request = WriterRequest(question="What are actinobacteria?", evidence_items=[])

    def client(prompt: str) -> str:
        assert "当前没有可加入上下文的本地证据条目" in prompt
        assert "claims 必须是空数组" in prompt
        return json.dumps(
            {
                "status": "SUPPORTED",
                "answer": "本地知识库未检索到可引用证据，以下是通用知识回答。放线菌常被视为天然产物来源。",
                "claims": [{"text": "模型不应保留这条无证据主张。", "evidence_refs": [], "claim_level": "descriptive"}],
                "evidence_refs": [],
                "limitations": ["这不是本地证据库支持的结论。"],
                "suggested_validations": ["检索真实文献和数据库。"],
            }
        )

    result = write_deepseek_answer(request, llm_client=client, allow_remote=True)

    assert result.writer_mode == "llm_general_knowledge"
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert result.answer.claims == []
    assert result.answer.evidence_refs == []
    assert "通用知识" in result.answer.limitations[0]


def test_empty_evidence_schema_failure_keeps_unstructured_general_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-placeholder")
    get_settings.cache_clear()
    request = WriterRequest(question="What are actinobacteria?", evidence_items=[])

    def client(_prompt: str) -> str:
        return "放线菌在通用知识中常被视为微生物天然产物的重要来源。"

    result = write_deepseek_answer(request, llm_client=client, allow_remote=True)

    assert result.writer_mode == "llm_general_knowledge"
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert result.answer.claims == []
    assert "放线菌" in result.answer.answer
    assert "结构化 JSON 校验" in result.answer.limitations[1]


def test_evidence_context_prompt_still_allows_general_knowledge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-placeholder")
    get_settings.cache_clear()
    request = _request()
    evidence_id = request.evidence_items[0].evidence_id

    def client(prompt: str) -> str:
        assert "始终利用通用科学知识" in prompt
        assert "本地知识库/检索证据如果存在，则作为额外上下文" in prompt
        assert str(evidence_id) in prompt
        return json.dumps(
            {
                "status": "PARTIALLY_SUPPORTED",
                "answer": "通用知识上，放线菌常与次级代谢物研究相关；本地证据只提供属级线索。",
                "claims": [
                    {
                        "text": "本地证据只支持属级候选线索。",
                        "evidence_refs": [str(evidence_id)],
                        "claim_level": "candidate",
                    }
                ],
                "evidence_refs": [str(evidence_id)],
                "limitations": ["通用知识不等同于本地证据支持。"],
                "suggested_validations": ["补充菌株级证据。"],
            }
        )

    result = write_deepseek_answer(request, llm_client=client, allow_remote=True)

    assert result.writer_mode == "llm_grounded"
    assert result.answer.status == AnswerStatus.PARTIALLY_SUPPORTED
    assert result.answer.claims[0].evidence_refs == [evidence_id]
    assert result.provider_metadata["grounding"] == "general_knowledge_with_local_evidence_context"


def test_deterministic_fallback_preserved_for_use_llm_false() -> None:
    answer = write_grounded_answer(_request(), use_llm=False)
    assert answer.writer_mode == "fallback"


def test_write_llm_answer_reports_accurate_mode_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("QWEN_API_KEY", "")
    get_settings.cache_clear()
    answer = write_llm_answer(_request())
    assert answer.writer_mode == "fallback"
    assert answer.provenance.get("llm_available") is False


def test_bounded_prompt_prohibits_invented_ids() -> None:
    prompt = build_bounded_prompt(_request())
    assert "Do NOT invent PMID" not in prompt
    assert "不得编造 PMID" in prompt
    assert "简体中文" in prompt
    assert "Feature_M123" in prompt


def test_config_check_never_includes_api_key_material() -> None:
    get_settings.cache_clear()
    report = check_llm_configuration()
    serialized = json.dumps(report)
    assert "sk-" not in serialized
