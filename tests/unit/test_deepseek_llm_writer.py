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
    assert result.writer_mode == "fallback_after_citation_failure"


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
    assert result.writer_mode == "fallback_after_constraint_violation"


def test_provider_failure_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-placeholder")
    get_settings.cache_clear()
    request = _request()

    def failing_client(_prompt: str) -> str:
        raise TimeoutError("provider timeout")

    result = write_deepseek_answer(request, llm_client=failing_client, allow_remote=True)
    assert result.writer_mode == "fallback_after_provider_error"


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
