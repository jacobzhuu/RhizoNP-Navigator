import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { ApiError, BackendUnavailableError, type EvidenceGradingResponse } from '../api/types'
import { Badge, distanceBadgeVariant, tierBadgeVariant } from '../components/Badge'
import { ErrorPanel, LimitationsPanel, WarningPanel } from '../components/Panels'
import { ProvenanceBlock } from '../components/ProvenanceBlock'

const DEFAULT_QUERY = 'Streptomyces'
const DEFAULT_LIT = 'Streptomyces hygroscopicus OS-2'
const DEFAULT_METHOD = '16S genus-level'

function isHighRisk(result: EvidenceGradingResponse): boolean {
  const dist = result.taxonomy_distance.toUpperCase()
  const tier = result.evidence_tier.toUpperCase()
  return dist.includes('SAME_GENUS') || tier === 'C' || result.warnings.length > 0
}

export function EvidenceGraderPage() {
  const [queryTaxon, setQueryTaxon] = useState(DEFAULT_QUERY)
  const [literatureTaxon, setLiteratureTaxon] = useState(DEFAULT_LIT)
  const [method, setMethod] = useState(DEFAULT_METHOD)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null)
  const [result, setResult] = useState<EvidenceGradingResponse | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.gradeTaxonomy({
        query_taxon: queryTaxon,
        literature_taxon: literatureTaxon,
        observation_method: method || null,
      })
      setResult(data)
    } catch (err) {
      if (err instanceof BackendUnavailableError || err instanceof ApiError) {
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
        <h1>Evidence Grader</h1>
        <p className="subtitle">Taxonomy-aware evidence grading with conservative claim limits</p>
      </header>

      <form className="card" onSubmit={handleSubmit}>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="query">Query Taxon</label>
            <input id="query" value={queryTaxon} onChange={(e) => setQueryTaxon(e.target.value)} required />
          </div>
          <div className="form-group">
            <label htmlFor="lit">Literature Taxon</label>
            <input id="lit" value={literatureTaxon} onChange={(e) => setLiteratureTaxon(e.target.value)} required />
          </div>
          <div className="form-group">
            <label htmlFor="method">Observation Method</label>
            <input id="method" value={method} onChange={(e) => setMethod(e.target.value)} />
          </div>
        </div>
        <button type="submit" className="btn" disabled={loading}>
          {loading ? 'Grading…' : 'Grade Evidence'}
        </button>
      </form>

      {loading && <p className="loading">Applying taxonomy policy…</p>}
      {error && <ErrorPanel message={error.message} detail={error.detail} />}

      {result && (
        <div className={`card${isHighRisk(result) ? ' highlight-card' : ''}`} style={isHighRisk(result) ? { borderColor: 'var(--color-warning-border)', background: 'var(--color-warning-bg)' } : undefined}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
            <Badge label={result.taxonomy_distance} variant={distanceBadgeVariant(result.taxonomy_distance)} />
            <Badge label={`Tier ${result.evidence_tier}`} variant={tierBadgeVariant(result.evidence_tier)} />
          </div>

          {result.taxonomy_distance.toUpperCase().includes('SAME_GENUS') && (
            <div className="panel-warning">
              <strong>SAME_GENUS distance detected</strong>
              Genus-level observations cannot support strain- or species-specific production claims.
            </div>
          )}

          <WarningPanel items={result.warnings} />
          <LimitationsPanel items={result.limitations} />

          <h3>Maximum Supported Claim</h3>
          <p>{result.max_supported_claim}</p>

          <div className="form-row" style={{ marginTop: '1rem' }}>
            <div className="form-group">
              <label>Query Taxon (normalized)</label>
              <pre style={{ margin: 0, fontSize: '0.8rem' }}>{JSON.stringify(result.query_taxon, null, 2)}</pre>
            </div>
            <div className="form-group">
              <label>Literature Taxon (normalized)</label>
              <pre style={{ margin: 0, fontSize: '0.8rem' }}>{JSON.stringify(result.literature_taxon, null, 2)}</pre>
            </div>
          </div>

          <ProvenanceBlock data={result.provenance} />
        </div>
      )}
    </>
  )
}
