import {
  type AskRequest,
  type AskResponse,
  type CorpusSummaryResponse,
  type EvidenceGradingRequest,
  type EvidenceGradingResponse,
  type GroundedAnswerRequest,
  type GroundedAnswerResponse,
  type HealthResponse,
  type HistoryDetailResponse,
  type HistoryKind,
  type HistoryListResponse,
  type ReadinessResponse,
  type NaturalProductLinkRequest,
  type NaturalProductLinkResponse,
  type OwnDataPipelineRequest,
  type OwnDataPipelineResponse,
  type ResultDemoRequest,
  type ResultInterpretationRequest,
  type ResultsInterpretationResponse,
  type SearchRequest,
  type SearchResponse,
  ApiError,
  BackendUnavailableError,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...init?.headers,
      },
    })
  } catch {
    throw new BackendUnavailableError()
  }

  if (!response.ok) {
    let detail: string | undefined
    try {
      const body = (await response.json()) as {
        detail?: string | unknown
        error?: { message?: string; detail?: string }
      }
      if (body.error?.message) {
        detail = body.error.detail ?? body.error.message
      } else if (typeof body.detail === 'string') {
        detail = body.detail
      } else if (body.detail != null) {
        detail = JSON.stringify(body.detail)
      }
    } catch {
      detail = response.statusText
    }
    throw new ApiError(`请求失败（${response.status}）`, response.status, detail)
  }

  return response.json() as Promise<T>
}

export const api = {
  health: () => request<HealthResponse>('/api/v1/health'),

  readiness: () => request<ReadinessResponse>('/api/v1/readiness'),

  ask: (body: AskRequest) =>
    request<AskResponse>('/api/v1/ask', { method: 'POST', body: JSON.stringify(body) }),

  getCorpusSummary: () => request<CorpusSummaryResponse>('/api/v1/corpus/summary'),

  searchLiterature: (body: SearchRequest) =>
    request<SearchResponse>('/api/v1/search', { method: 'POST', body: JSON.stringify(body) }),

  gradeTaxonomy: (body: EvidenceGradingRequest) =>
    request<EvidenceGradingResponse>('/api/v1/taxonomy/grade', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  linkNaturalProducts: (body: NaturalProductLinkRequest) =>
    request<NaturalProductLinkResponse>('/api/v1/natural-products/link', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  runOwnDataPipeline: (body: OwnDataPipelineRequest) =>
    request<OwnDataPipelineResponse>('/api/v1/own-data/pipeline', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  interpretResult: (body: ResultInterpretationRequest) =>
    request<ResultsInterpretationResponse>('/api/v1/results/interpret', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  runResultsDemo: (body: ResultDemoRequest = {}) =>
    request<ResultsInterpretationResponse>('/api/v1/results/demo', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  writeAnswer: (body: GroundedAnswerRequest) =>
    request<GroundedAnswerResponse>('/api/v1/writer/answer', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  listHistory: (params: { kind?: HistoryKind; limit?: number; offset?: number } = {}) => {
    const search = new URLSearchParams()
    if (params.kind) search.set('kind', params.kind)
    if (params.limit != null) search.set('limit', String(params.limit))
    if (params.offset != null) search.set('offset', String(params.offset))
    const query = search.toString()
    return request<HistoryListResponse>(`/api/v1/history${query ? `?${query}` : ''}`)
  },

  getHistory: (historyId: string) =>
    request<HistoryDetailResponse>(`/api/v1/history/${historyId}`),
}
