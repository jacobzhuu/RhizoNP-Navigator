from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str


class ApiErrorBody(BaseModel):
    code: str
    message: str
    detail: str | None = None


class ApiErrorResponse(BaseModel):
    error: ApiErrorBody


class ReadinessDatabaseResponse(BaseModel):
    connected: bool
    backend: str


class ReadinessCorpusResponse(BaseModel):
    paper_count: int
    chunk_count: int
    has_real_corpus: bool


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded", "unavailable"]
    database: ReadinessDatabaseResponse
    corpus: ReadinessCorpusResponse
    embedding_provider: str
    runtime_mode: str
    warnings: list[str]


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


class CorpusCountItemResponse(BaseModel):
    value: str
    count: int


class CorpusSamplePaperResponse(BaseModel):
    title: str
    year: int | None
    journal: str | None
    doi: str | None
    pmid: str | None
    source_url: str | None


class CorpusSummaryResponse(BaseModel):
    paper_count: int
    paper_chunk_count: int
    retrievable_tables: list[str]
    retrieval_modes: list[str]
    section_counts: dict[str, int]
    source_type_counts: dict[str, int]
    real_chunk_count: int
    fixture_chunk_count: int
    structured_counts: dict[str, int]
    top_taxa: list[CorpusCountItemResponse]
    top_compounds: list[CorpusCountItemResponse]
    top_hosts: list[CorpusCountItemResponse]
    sample_papers: list[CorpusSamplePaperResponse]


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
    taxonomy_source: str | None = None


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
    natural_product_source: str = "auto"


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
    natural_product_source: str
    rows: list[NaturalProductLinkRowResponse]


class OwnDataPipelineRequest(BaseModel):
    data_dir: str | None = None
    enable_literature_retrieval: bool = False
    retrieval_mode: str = "hybrid_rerank"
    top_k: int = 5
    max_queries: int = 3
    natural_product_source: str = "auto"
    taxonomy_source: str = "auto"
    enable_grounded_writer: bool = False


class OwnDataPipelineResponse(BaseModel):
    association_count: int
    results: list[dict[str, Any]]
    provenance: dict[str, Any]


class ResultInterpretationRequest(BaseModel):
    taxon: str = Field(min_length=1, max_length=300)
    metabolite: str = Field(min_length=1, max_length=300)
    association_direction: str = "positive"
    effect_size: float
    p_value: float | None = None
    observation_method: str = "16S genus-level"
    use_llm: bool | None = None
    retrieval_mode: Literal["bm25", "dense", "hybrid", "hybrid_rerank"] = "hybrid_rerank"
    top_k: int = Field(default=5, ge=1, le=20)
    max_queries: int = Field(default=3, ge=1, le=5)
    natural_product_source: str = "auto"
    taxonomy_source: str = "auto"


class ResultDemoRequest(BaseModel):
    use_llm: bool | None = None
    retrieval_mode: Literal["bm25", "dense", "hybrid", "hybrid_rerank"] = "hybrid_rerank"
    top_k: int = Field(default=5, ge=1, le=20)
    max_queries: int = Field(default=3, ge=1, le=5)
    natural_product_source: str = "auto"
    taxonomy_source: str = "auto"


class ResultsInterpretationResponse(BaseModel):
    finding_count: int
    interpretations: list[dict[str, Any]]
    provenance: dict[str, Any]
    history_id: uuid.UUID | None = None


class WriterEvidenceInputRequest(BaseModel):
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


class WriterClaimResponse(BaseModel):
    text: str
    evidence_refs: list[uuid.UUID]
    claim_level: str


class GroundedAnswerRequest(BaseModel):
    question: str
    evidence_items: list[WriterEvidenceInputRequest] = Field(default_factory=list)
    taxonomy_warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    use_llm: bool | None = None
    retrieve_evidence: bool = False
    retrieval_query: str | None = None
    retrieval_mode: str = "bm25"
    top_k: int = 5
    query_taxon: str | None = None
    observation_method: str | None = None


class GroundedAnswerResponse(BaseModel):
    status: str
    answer: str
    claims: list[WriterClaimResponse]
    evidence_refs: list[uuid.UUID]
    limitations: list[str]
    suggested_validations: list[str]
    writer_mode: str
    provenance: dict[str, Any]
    citation_validation: dict[str, Any] | None = None
    faithfulness_diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    answer_mode: str | None = None
    evidence_status: str | None = None
    llm_status: str | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    retrieval_mode: Literal["bm25", "dense", "hybrid", "hybrid_rerank"] = "hybrid_rerank"
    top_k: int = Field(default=5, ge=1, le=20)
    max_queries: int = Field(default=3, ge=1, le=5)
    use_llm: bool | None = None

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("question must be at least 3 characters after trimming whitespace")
        return stripped


class AskPlannedQueryResponse(BaseModel):
    query_text: str
    query_type: str
    rationale: str


class AskQuestionPlanResponse(BaseModel):
    original_question: str
    intent: str
    entities: dict[str, list[str]]
    synonym_expansions: dict[str, list[str]]
    planned_queries: list[AskPlannedQueryResponse]
    warnings: list[str]
    planner_mode: str


class AskRetrievalHitResponse(BaseModel):
    query_text: str
    query_index: int
    paper_id: str
    chunk_id: str
    title: str
    supporting_text: str
    pmid: str | None = None
    doi: str | None = None
    source_url: str | None = None
    journal: str | None = None
    year: int | None = None
    section: str
    retrieval_mode: str
    retrieval_score: float
    matched_terms: list[str]
    provenance: dict[str, Any]
    source_type: str
    is_fixture: bool
    taxonomy_grading: dict[str, Any] | None = None


class AskResponse(BaseModel):
    question_plan: AskQuestionPlanResponse
    retrieval_mode: str
    retrieval_hits: list[AskRetrievalHitResponse]
    answer: GroundedAnswerResponse
    evidence_items: list[dict[str, Any]]
    citation_validation: dict[str, Any]
    faithfulness_diagnostics: list[dict[str, Any]]
    provenance: dict[str, Any]
    history_id: uuid.UUID | None = None


class HistoryListItemResponse(BaseModel):
    history_id: uuid.UUID
    kind: Literal["ask", "results"]
    title: str
    status: str
    summary: str | None = None
    created_at: str


class HistoryListResponse(BaseModel):
    items: list[HistoryListItemResponse]
    total: int
    limit: int
    offset: int


class HistoryDetailResponse(BaseModel):
    history_id: uuid.UUID
    kind: Literal["ask", "results"]
    created_at: str
    request: dict[str, Any]
    response: dict[str, Any]
