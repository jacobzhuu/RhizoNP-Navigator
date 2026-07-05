import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import {
  ApiError,
  BackendUnavailableError,
  type GroundedAnswerRequest,
  type GroundedAnswerResponse,
} from '../api/types'
import { Badge, tierBadgeVariant } from '../components/Badge'
import { ErrorPanel, InfoPanel, LimitationsPanel, WarningPanel } from '../components/Panels'
import { ProvenanceBlock } from '../components/ProvenanceBlock'

const DEMO_REQUEST: GroundedAnswerRequest = {
  question: 'What is supported by the evidence?',
  evidence_items: [
    {
      evidence_id: '00000000-0000-4000-8000-000000000001',
      claim_type: 'association',
      predicate: 'correlates_with',
      object_literal: 'Feature_M123',
      evidence_tier: 'same_genus',
      directness: 'indirect',
      confidence: 0.6,
      supporting_span: 'genus-level correlation only',
      provenance: { fixture: true },
    },
  ],
  taxonomy_warnings: ['Genus-level 16S cannot support strain-level production claims.'],
  limitations: ['Correlation is not causation.'],
  use_llm: false,
}

function statusVariant(status: string): 'supported' | 'partial' | 'insufficient' | 'mode' {
  if (status === 'SUPPORTED') return 'supported'
  if (status === 'PARTIALLY_SUPPORTED') return 'partial'
  if (status === 'INSUFFICIENT_EVIDENCE' || status === 'CONFLICTING_EVIDENCE') return 'insufficient'
  return 'mode'
}

export function GroundedReportPage() {
  const [jsonInput, setJsonInput] = useState(JSON.stringify(DEMO_REQUEST, null, 2))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null)
  const [result, setResult] = useState<GroundedAnswerResponse | null>(null)
  const [lastWarnings, setLastWarnings] = useState<string[]>([])

  function loadDemo() {
    setJsonInput(JSON.stringify(DEMO_REQUEST, null, 2))
    setResult(null)
    setError(null)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const body = JSON.parse(jsonInput) as GroundedAnswerRequest
      setLastWarnings(body.taxonomy_warnings ?? [])
      const data = await api.writeAnswer(body)
      setResult(data)
    } catch (err) {
      if (err instanceof SyntaxError) {
        setError({ message: 'Invalid JSON input', detail: err.message })
      } else if (err instanceof BackendUnavailableError || err instanceof ApiError) {
        setError({ message: err.message, detail: err instanceof ApiError ? err.detail : undefined })
      } else {
        setError({ message: 'Unexpected error', detail: String(err) })
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <header className="page-header">
        <h1>Grounded Report</h1>
        <p className="subtitle">Evidence-bound scientific answers with claim tracing</p>
      </header>

      <InfoPanel>
        Writer uses deterministic fallback in MVP (<code>use_llm: false</code>). Remote LLM calls are disabled.
      </InfoPanel>

      <form className="card" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="json">Request JSON</label>
          <textarea
            id="json"
            value={jsonInput}
            onChange={(e) => setJsonInput(e.target.value)}
            rows={14}
            style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}
          />
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button type="submit" className="btn" disabled={loading}>
            {loading ? 'Generating…' : 'Generate Report'}
          </button>
          <button type="button" className="btn btn-secondary" onClick={loadDemo}>
            Load Demo Example
          </button>
        </div>
      </form>

      {loading && <p className="loading">Writing grounded answer…</p>}
      {error && <ErrorPanel message={error.message} detail={error.detail} />}

      {result && (
        <div className="card">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
            <Badge label={result.status} variant={statusVariant(result.status)} />
            <Badge label={`Writer: ${result.writer_mode}`} variant="mode" />
          </div>

          <h3>Answer</h3>
          <p>{result.answer}</p>

          {result.claims.length > 0 && (
            <>
              <h3>Claims</h3>
              <ul>
                {result.claims.map((claim, i) => (
                  <li key={i} style={{ marginBottom: '0.5rem' }}>
                    <Badge label={claim.claim_level} variant={tierBadgeVariant(claim.claim_level)} />
                    {' '}{claim.text}
                    <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: '0.25rem' }}>
                      Evidence refs: {claim.evidence_refs.join(', ')}
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}

          {result.evidence_refs.length > 0 && (
            <p style={{ fontSize: '0.875rem' }}>
              <strong>Evidence refs:</strong> {result.evidence_refs.join(', ')}
            </p>
          )}

          <WarningPanel title="Taxonomy Warnings" items={lastWarnings} />
          <LimitationsPanel items={result.limitations} />

          {result.suggested_validations.length > 0 && (
            <>
              <h3>Suggested Validations</h3>
              <ul>
                {result.suggested_validations.map((v, i) => (
                  <li key={i}>{v}</li>
                ))}
              </ul>
            </>
          )}

          <ProvenanceBlock data={result.provenance} />
        </div>
      )}
    </>
  )
}
