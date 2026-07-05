import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { ApiError, BackendUnavailableError, type NaturalProductLinkResponse } from '../api/types'
import { Badge, distanceBadgeVariant, tierBadgeVariant } from '../components/Badge'
import { ErrorPanel, InfoPanel } from '../components/Panels'
import { isFixtureRecord, ProvenanceBlock } from '../components/ProvenanceBlock'

const DEFAULT_QUERY = 'Streptomyces'
const DEFAULT_METABOLITE = 'FixturePolyketide-A'

export function NaturalProductsPage() {
  const [queryTaxon, setQueryTaxon] = useState(DEFAULT_QUERY)
  const [metabolite, setMetabolite] = useState(DEFAULT_METABOLITE)
  const [method, setMethod] = useState('16S genus-level')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null)
  const [result, setResult] = useState<NaturalProductLinkResponse | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.linkNaturalProducts({
        query_taxon: queryTaxon,
        metabolite_name: metabolite || null,
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
        <h1>Natural Product Linking</h1>
        <p className="subtitle">Rank candidate compounds by taxonomy distance and evidence tier</p>
      </header>

      <InfoPanel>
        Candidate matrix uses synthetic NP fixture records (<code>synthetic_fixture</code> database).
        Rows marked as fixture are not real literature-derived associations.
      </InfoPanel>

      <form className="card" onSubmit={handleSubmit}>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="query">Query Taxon</label>
            <input id="query" value={queryTaxon} onChange={(e) => setQueryTaxon(e.target.value)} required />
          </div>
          <div className="form-group">
            <label htmlFor="metabolite">Metabolite Name</label>
            <input id="metabolite" value={metabolite} onChange={(e) => setMetabolite(e.target.value)} placeholder="Optional" />
          </div>
          <div className="form-group">
            <label htmlFor="method">Observation Method</label>
            <input id="method" value={method} onChange={(e) => setMethod(e.target.value)} />
          </div>
        </div>
        <button type="submit" className="btn" disabled={loading}>
          {loading ? 'Linking…' : 'Link Candidates'}
        </button>
      </form>

      {loading && <p className="loading">Building candidate matrix…</p>}
      {error && <ErrorPanel message={error.message} detail={error.detail} />}

      {result && (
        <div className="card">
          <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', marginBottom: '1rem' }}>
            Query: {result.query_taxon}
            {result.metabolite_name && ` · Metabolite: ${result.metabolite_name}`}
            {' · '}{result.rows.length} candidate(s)
          </p>

          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Compound</th>
                  <th>Producer</th>
                  <th>Match</th>
                  <th>Distance</th>
                  <th>Tier</th>
                  <th>Score</th>
                  <th>Status</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row) => {
                  const fixture = isFixtureRecord(row.provenance)
                  const highlight = row.taxonomy_distance.toUpperCase().includes('SAME_GENUS') || row.evidence_tier === 'C'
                  return (
                    <tr key={row.rank} className={highlight ? 'highlight-row' : undefined}>
                      <td>{row.rank}</td>
                      <td>{row.compound_name}</td>
                      <td>{row.producer_taxon}</td>
                      <td>{row.compound_match ? '✓' : '—'}</td>
                      <td><Badge label={row.taxonomy_distance} variant={distanceBadgeVariant(row.taxonomy_distance)} /></td>
                      <td><Badge label={row.evidence_tier} variant={tierBadgeVariant(row.evidence_tier)} /></td>
                      <td>{row.score.toFixed(3)}</td>
                      <td>{row.status}</td>
                      <td>{fixture ? <Badge label="Fixture" variant="fixture" /> : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {result.rows.map((row) => (
            <div key={`detail-${row.rank}`} className="card" style={{ marginTop: '1rem', fontSize: '0.875rem' }}>
              <strong>#{row.rank} {row.compound_name}</strong>
              {row.warnings.length > 0 && (
                <ul style={{ color: 'var(--color-warning-text)', margin: '0.5rem 0' }}>
                  {row.warnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              )}
              {row.limitations.length > 0 && (
                <ul style={{ color: 'var(--color-text-muted)', margin: '0.5rem 0' }}>
                  {row.limitations.map((l, i) => <li key={i}>{l}</li>)}
                </ul>
              )}
              <ProvenanceBlock data={row.provenance} />
            </div>
          ))}
        </div>
      )}
    </>
  )
}
