from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AnswerStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"


class EvidenceInput(BaseModel):
    evidence_id: uuid.UUID
    claim_type: str
    predicate: str
    object_literal: str | None = None
    evidence_tier: str
    directness: str = "indirect"
    confidence: float = 0.5
    supporting_span: str | None = None
    taxonomy_distance: str | None = None
    warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class Claim(BaseModel):
    text: str
    evidence_refs: list[uuid.UUID]
    claim_level: str = "descriptive"


class WriterRequest(BaseModel):
    question: str
    evidence_items: list[EvidenceInput]
    taxonomy_warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class GroundedAnswer(BaseModel):
    status: AnswerStatus
    answer: str
    claims: list[Claim]
    evidence_refs: list[uuid.UUID]
    limitations: list[str]
    suggested_validations: list[str] = Field(default_factory=list)
    writer_mode: str = "fallback"
    provenance: dict[str, Any] = Field(default_factory=dict)
