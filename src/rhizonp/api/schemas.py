from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


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


class SearchFiltersRequest(BaseModel):
    year_from: int | None = None
    year_to: int | None = None
    sections: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)
    dois: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    journals: list[str] = Field(default_factory=list)
    taxa: list[str] = Field(default_factory=list)
    compounds: list[str] = Field(default_factory=list)
    host: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str
    filters: SearchFiltersRequest = Field(default_factory=SearchFiltersRequest)
    top_k: int = 10
    retrieval_mode: str = "bm25"
    bm25_weight: float = 0.5
    dense_weight: float = 0.5
    reranker_weight: float = 1.0


class SearchTraceResponse(BaseModel):
    chunk_id: uuid.UUID
    paper_id: uuid.UUID
    doi: str | None
    source_url: str | None
    section: str
    char_start: int
    char_end: int


class SearchResultResponse(BaseModel):
    rank: int
    score: float
    text: str
    matched_terms: list[str]
    score_components: dict[str, Any]
    trace: SearchTraceResponse


class SearchResponse(BaseModel):
    run_id: uuid.UUID
    retrieval_mode: str
    results: list[SearchResultResponse]


class NormalizedTaxonResponse(BaseModel):
    canonical_name: str
    rank: str | None
    strain: str | None
    species: str | None
    genus: str | None
    normalization_status: str
    confidence: float


class EvidenceGradingRequest(BaseModel):
    query_taxon: str
    literature_taxon: str
    observation_method: str | None = None


class EvidenceGradingResponse(BaseModel):
    query_taxon: NormalizedTaxonResponse
    literature_taxon: NormalizedTaxonResponse
    taxonomy_distance: str
    evidence_tier: str
    warnings: list[str]
    limitations: list[str]
    max_supported_claim: str
    provenance: dict[str, Any]


class NaturalProductLinkRequest(BaseModel):
    query_taxon: str
    metabolite_name: str | None = None
    observation_method: str | None = None


class NaturalProductLinkRowResponse(BaseModel):
    rank: int
    query_taxon: str
    compound_name: str
    producer_taxon: str
    taxonomy_distance: str
    evidence_tier: str
    compound_match: bool
    evidence_count: int
    score: float
    status: str
    bioactivity: dict[str, Any] | None
    warnings: list[str]
    limitations: list[str]
    provenance: dict[str, Any]


class NaturalProductLinkResponse(BaseModel):
    query_taxon: str
    metabolite_name: str | None
    rows: list[NaturalProductLinkRowResponse]


class OwnDataPipelineRequest(BaseModel):
    data_dir: str | None = None


class OwnDataPipelineResponse(BaseModel):
    association_count: int
    results: list[dict[str, Any]]
    provenance: dict[str, Any]
