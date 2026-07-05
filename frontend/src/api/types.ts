export interface HealthResponse {
  status: string
}

export interface SearchFilters {
  year_from?: number | null
  year_to?: number | null
  sections?: string[]
  source_types?: string[]
  dois?: string[]
  source_urls?: string[]
  journals?: string[]
  taxa?: string[]
  compounds?: string[]
  host?: string[]
}

export interface SearchRequest {
  query: string
  filters?: SearchFilters
  top_k?: number
  retrieval_mode?: string
  bm25_weight?: number
  dense_weight?: number
  reranker_weight?: number
}

export interface SearchTrace {
  chunk_id: string
  paper_id: string
  doi: string | null
  source_url: string | null
  section: string
  char_start: number
  char_end: number
}

export interface SearchResult {
  rank: number
  score: number
  text: string
  matched_terms: string[]
  score_components: Record<string, unknown>
  trace: SearchTrace
}

export interface SearchResponse {
  run_id: string
  retrieval_mode: string
  results: SearchResult[]
}

export interface NormalizedTaxon {
  canonical_name: string
  rank: string | null
  strain: string | null
  species: string | null
  genus: string | null
  normalization_status: string
  confidence: number
}

export interface EvidenceGradingRequest {
  query_taxon: string
  literature_taxon: string
  observation_method?: string | null
}

export interface EvidenceGradingResponse {
  query_taxon: NormalizedTaxon
  literature_taxon: NormalizedTaxon
  taxonomy_distance: string
  evidence_tier: string
  warnings: string[]
  limitations: string[]
  max_supported_claim: string
  provenance: Record<string, unknown>
}

export interface NaturalProductLinkRequest {
  query_taxon: string
  metabolite_name?: string | null
  observation_method?: string | null
}

export interface NaturalProductLinkRow {
  rank: number
  query_taxon: string
  compound_name: string
  producer_taxon: string
  taxonomy_distance: string
  evidence_tier: string
  compound_match: boolean
  evidence_count: number
  score: number
  status: string
  bioactivity: Record<string, unknown> | null
  warnings: string[]
  limitations: string[]
  provenance: Record<string, unknown>
}

export interface NaturalProductLinkResponse {
  query_taxon: string
  metabolite_name: string | null
  rows: NaturalProductLinkRow[]
}

export interface OwnDataPipelineRequest {
  data_dir?: string | null
}

export interface OwnDataPipelineResponse {
  association_count: number
  results: Record<string, unknown>[]
  provenance: Record<string, unknown>
}

export interface WriterEvidenceInput {
  evidence_id: string
  claim_type: string
  predicate: string
  object_literal?: string | null
  evidence_tier: string
  directness?: string
  confidence?: number
  supporting_span?: string | null
  taxonomy_distance?: string | null
  warnings?: string[]
  provenance?: Record<string, unknown>
}

export interface GroundedAnswerRequest {
  question: string
  evidence_items: WriterEvidenceInput[]
  taxonomy_warnings?: string[]
  limitations?: string[]
  use_llm?: boolean
}

export interface WriterClaim {
  text: string
  evidence_refs: string[]
  claim_level: string
}

export interface GroundedAnswerResponse {
  status: string
  answer: string
  claims: WriterClaim[]
  evidence_refs: string[]
  limitations: string[]
  suggested_validations: string[]
  writer_mode: string
  provenance: Record<string, unknown>
}

export class ApiError extends Error {
  status: number
  detail?: string

  constructor(message: string, status: number, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export class BackendUnavailableError extends Error {
  constructor(message = 'Backend unavailable. Start the API on port 8000.') {
    super(message)
    this.name = 'BackendUnavailableError'
  }
}
