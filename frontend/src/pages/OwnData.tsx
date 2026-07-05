import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { ApiError, BackendUnavailableError, type OwnDataPipelineResponse } from '../api/types'
import { Badge, tierBadgeVariant } from '../components/Badge'
import { ErrorPanel, InfoPanel, LimitationsPanel } from '../components/Panels'
import { ProvenanceBlock } from '../components/ProvenanceBlock'

interface AssociationResult {
  association_id?: string
  source_raw_label?: string
  target_raw_label?: string
  score?: number
  adjusted_p?: number
  method?: string
  taxonomy_grading?: {
    taxonomy_distance?: string
    evidence_tier?: string
    max_supported_claim?: string
    warnings?: string[]
    limitations?: string[]
  }
  candidate_links?: {
    query_taxon?: string
    metabolite_name?: string | null
    rows?: Array<{
      rank: number
      compound_name: string
      producer_taxon: string
      evidence_tier: string
      score: number
      status: string
      compound_match: boolean
    }>
  }
  limitations?: string[]
}

export function OwnDataPage() {
  const [dataDir, setDataDir] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null)
  const [result, setResult] = useState<OwnDataPipelineResponse | null>(null)

  async function runPipeline(useDemo: boolean) {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const body = useDemo ? {} : { data_dir: dataDir || null }
      const data = await api.runOwnDataPipeline(body)
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

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    runPipeline(false)
  }

  const associations = (result?.results ?? []) as AssociationResult[]

  return (
    <>
      <header className="page-header">
        <h1>Own-data Workspace</h1>
        <p className="subtitle">Omics association CSV → taxonomy grading → candidate linking</p>
      </header>

      <InfoPanel>
        No browser upload in MVP. Run demo fixtures from <code>data/fixtures/own_data_demo</code> or
        specify a local directory path if the backend can read it.
      </InfoPanel>

      <form className="card" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="datadir">Local Data Directory (optional)</label>
          <input
            id="datadir"
            value={dataDir}
            onChange={(e) => setDataDir(e.target.value)}
            placeholder="Leave empty for demo fixtures"
          />
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button type="button" className="btn" onClick={() => runPipeline(true)} disabled={loading}>
            Run Demo Data
          </button>
          <button type="submit" className="btn btn-secondary" disabled={loading || !dataDir.trim()}>
            Run Custom Directory
          </button>
        </div>
      </form>

      {loading && <p className="loading">Running pipeline…</p>}
      {error && <ErrorPanel message={error.message} detail={error.detail} />}

      {result && (
        <>
          <div className="card">
            <strong>{result.association_count}</strong> association(s) processed
            <ProvenanceBlock data={result.provenance} />
          </div>

          {associations.map((assoc, idx) => (
            <div key={assoc.association_id ?? idx} className="card">
              <h3>
                {assoc.source_raw_label} ↔ {assoc.target_raw_label}
              </h3>
              <div className="result-meta">
                <span>Score: {assoc.score?.toFixed(4) ?? '—'}</span>
                <span>Adj. p: {assoc.adjusted_p?.toFixed(4) ?? '—'}</span>
                <span>Method: {assoc.method ?? '—'}</span>
              </div>

              {assoc.taxonomy_grading && (
                <div style={{ marginTop: '1rem' }}>
                  <h4 style={{ fontSize: '0.95rem' }}>Taxonomy Grading</h4>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
                    {assoc.taxonomy_grading.taxonomy_distance && (
                      <Badge label={assoc.taxonomy_grading.taxonomy_distance} variant="same-genus" />
                    )}
                    {assoc.taxonomy_grading.evidence_tier && (
                      <Badge label={`Tier ${assoc.taxonomy_grading.evidence_tier}`} variant={tierBadgeVariant(assoc.taxonomy_grading.evidence_tier)} />
                    )}
                  </div>
                  {assoc.taxonomy_grading.max_supported_claim && (
                    <p style={{ fontSize: '0.875rem' }}>{assoc.taxonomy_grading.max_supported_claim}</p>
                  )}
                  {assoc.taxonomy_grading.warnings && assoc.taxonomy_grading.warnings.length > 0 && (
                    <ul style={{ color: 'var(--color-warning-text)', fontSize: '0.875rem' }}>
                      {assoc.taxonomy_grading.warnings.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  )}
                </div>
              )}

              {assoc.candidate_links?.rows && assoc.candidate_links.rows.length > 0 && (
                <div style={{ marginTop: '1rem', overflowX: 'auto' }}>
                  <h4 style={{ fontSize: '0.95rem' }}>Candidate Matrix</h4>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Rank</th>
                        <th>Compound</th>
                        <th>Producer</th>
                        <th>Match</th>
                        <th>Tier</th>
                        <th>Score</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {assoc.candidate_links.rows.map((row) => (
                        <tr key={row.rank}>
                          <td>{row.rank}</td>
                          <td>{row.compound_name}</td>
                          <td>{row.producer_taxon}</td>
                          <td>{row.compound_match ? '✓' : '—'}</td>
                          <td><Badge label={row.evidence_tier} variant={tierBadgeVariant(row.evidence_tier)} /></td>
                          <td>{row.score.toFixed(3)}</td>
                          <td>{row.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <LimitationsPanel items={assoc.limitations ?? []} />
            </div>
          ))}

          {result.association_count > 0 && (
            <div className="card">
              <h3>Export</h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                Copy JSON below for notebooks or reports.
              </p>
              <pre style={{ maxHeight: '300px', overflow: 'auto' }}>
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          )}
        </>
      )}
    </>
  )
}
