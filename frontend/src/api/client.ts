import {
  type EvidenceGradingRequest,
  type EvidenceGradingResponse,
  type GroundedAnswerRequest,
  type GroundedAnswerResponse,
  type HealthResponse,
  type NaturalProductLinkRequest,
  type NaturalProductLinkResponse,
  type OwnDataPipelineRequest,
  type OwnDataPipelineResponse,
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
      const body = (await response.json()) as { detail?: string }
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      detail = response.statusText
    }
    throw new ApiError(`请求失败（${response.status}）`, response.status, detail)
  }

  return response.json() as Promise<T>
}

export const api = {
  health: () => request<HealthResponse>('/api/v1/health'),

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

  writeAnswer: (body: GroundedAnswerRequest) =>
    request<GroundedAnswerResponse>('/api/v1/writer/answer', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}
