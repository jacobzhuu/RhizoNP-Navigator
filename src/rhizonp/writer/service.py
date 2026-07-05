from __future__ import annotations

from rhizonp.config import get_settings
from rhizonp.writer.fallback_writer import write_fallback_answer
from rhizonp.writer.models import GroundedAnswer, WriterRequest


def write_llm_answer(request: WriterRequest) -> GroundedAnswer:
    """Optional LLM writer placeholder.

    The project keeps LLM synthesis optional and offline by default. When no API key
    is configured, this function falls back to the deterministic writer.
    """
    settings = get_settings()
    if not settings.deepseek_api_key and not settings.qwen_api_key:
        answer = write_fallback_answer(request)
        return answer.model_copy(
            update={
                "provenance": {
                    **answer.provenance,
                    "llm_requested": True,
                    "llm_available": False,
                }
            }
        )

    # Keep MVP deterministic: do not call remote APIs in default tests or demos.
    answer = write_fallback_answer(request)
    return answer.model_copy(
        update={
            "writer_mode": "llm_fallback",
            "provenance": {
                **answer.provenance,
                "llm_requested": True,
                "llm_available": True,
                "llm_execution": "disabled_in_mvp",
            },
        }
    )


def write_grounded_answer(
    request: WriterRequest,
    *,
    use_llm: bool = False,
) -> GroundedAnswer:
    if use_llm:
        return write_llm_answer(request)
    return write_fallback_answer(request)
