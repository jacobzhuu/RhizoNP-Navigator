from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class TaxonResponse(BaseModel):
    taxon_id: uuid.UUID
    canonical_name: str
    rank: str | None
    strain: str | None
    species: str | None
    genus: str | None
    family: str | None
    external_ids: dict[str, Any]
    normalization_status: str


class CompoundResponse(BaseModel):
    compound_id: uuid.UUID
    canonical_name: str
    smiles: str | None
    inchikey: str | None
    formula: str | None
    compound_class: str | None
    structure_status: str
    external_ids: dict[str, Any]


class EvidenceItemResponse(BaseModel):
    evidence_id: uuid.UUID
    claim_type: str
    subject_entity_type: str
    subject_entity_id: uuid.UUID
    predicate: str
    object_entity_type: str | None
    object_entity_id: uuid.UUID | None
    object_literal: str | None
    source_type: str
    source_id: uuid.UUID
    evidence_tier: str
    directness: str
    extraction_method: str
    confidence: float
    supporting_span: str | None
    provenance: dict[str, Any]


class CandidateLinkResponse(BaseModel):
    candidate_id: uuid.UUID
    source_entity_type: str
    source_entity_id: uuid.UUID
    relation: str
    target_entity_type: str
    target_entity_id: uuid.UUID
    internal_evidence_score: float | None
    external_evidence_score: float | None
    taxonomy_distance: str | None
    evidence_tier: str
    status: str
    rationale: dict[str, Any]


class OmicsAssociationResponse(BaseModel):
    association_id: uuid.UUID
    dataset_id: uuid.UUID
    source_entity_type: str
    source_entity_id: uuid.UUID | None
    source_raw_label: str
    target_entity_type: str
    target_entity_id: uuid.UUID | None
    target_raw_label: str
    score: float
    adjusted_p: float | None
    method: str
    direction: str | None
    treatment: str | None
    timepoint: str | None
    metadata: dict[str, Any]
