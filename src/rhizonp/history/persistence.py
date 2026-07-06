from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from rhizonp.api.schemas import (
    AskRequest,
    AskResponse,
    ResultInterpretationRequest,
    ResultsInterpretationResponse,
)
from rhizonp.domain.models import InteractionHistory
from rhizonp.storage.repositories import InteractionHistoryRepository

_SUMMARY_MAX_LEN = 200


def _truncate_summary(text: str | None) -> str | None:
    if not text:
        return None
    stripped = text.strip()
    if not stripped:
        return None
    if len(stripped) <= _SUMMARY_MAX_LEN:
        return stripped
    return stripped[: _SUMMARY_MAX_LEN - 1] + "…"


def _ask_summary_fields(request: AskRequest, response: AskResponse) -> tuple[str, str, str | None]:
    title = request.question
    status = response.answer.status
    summary = _truncate_summary(response.answer.answer)
    return title, status, summary


def _results_summary_fields(
    request: ResultInterpretationRequest,
    response: ResultsInterpretationResponse,
) -> tuple[str, str, str | None]:
    title = f"{request.taxon} · {request.metabolite}"
    status = "UNKNOWN"
    summary: str | None = None
    if response.interpretations:
        first = response.interpretations[0]
        status = str(first.get("status") or first.get("status_label") or "UNKNOWN")
        finding = first.get("finding")
        if isinstance(finding, dict):
            summary = _truncate_summary(str(finding.get("text") or ""))
        if summary is None:
            summary = _truncate_summary(str(first.get("status_label") or ""))
    return title, status, summary


def _model_dump(payload: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json")
    return payload


def persist_ask_history(
    session: Session,
    request: AskRequest,
    response: AskResponse,
) -> uuid.UUID:
    title, status, summary = _ask_summary_fields(request, response)
    request_payload = _model_dump(request)
    response_payload = _model_dump(response)
    record = InteractionHistory(
        kind="ask",
        title=title,
        status=status,
        summary=summary,
        request_payload=request_payload,
        response_payload=response_payload,
    )
    InteractionHistoryRepository(session).add(record)
    return record.history_id


def persist_results_history(
    session: Session,
    request: ResultInterpretationRequest,
    response: ResultsInterpretationResponse,
) -> uuid.UUID:
    title, status, summary = _results_summary_fields(request, response)
    record = InteractionHistory(
        kind="results",
        title=title,
        status=status,
        summary=summary,
        request_payload=_model_dump(request),
        response_payload=_model_dump(response),
    )
    InteractionHistoryRepository(session).add(record)
    return record.history_id


def list_interaction_history(
    session: Session,
    *,
    kind: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[InteractionHistory], int]:
    repo = InteractionHistoryRepository(session)
    items = repo.list_by_kind(kind=kind, limit=limit, offset=offset)
    total = repo.count_by_kind(kind=kind)
    return items, total


def get_interaction_history(session: Session, history_id: uuid.UUID) -> InteractionHistory | None:
    return InteractionHistoryRepository(session).get_by_id(history_id)
