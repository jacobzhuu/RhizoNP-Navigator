from __future__ import annotations

from rhizonp.config import get_settings
from rhizonp.writer.fallback_writer import write_fallback_answer
from rhizonp.writer.llm_writer import write_deepseek_answer
from rhizonp.writer.models import GroundedAnswer, WriterRequest


def write_llm_answer(request: WriterRequest) -> GroundedAnswer:
    """DeepSeek-backed grounded writer with citation and constraint gates."""
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

    result = write_deepseek_answer(request, allow_remote=True)
    return result.answer


def write_grounded_answer(
    request: WriterRequest,
    *,
    use_llm: bool = False,
) -> GroundedAnswer:
    if use_llm:
        return write_llm_answer(request)
    return write_fallback_answer(request)
