import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { ApiError, BackendUnavailableError, type NaturalProductLinkResponse } from '../api/types'
import { Badge, distanceBadgeVariant, tierBadgeVariant } from '../components/Badge'
import { ErrorPanel, InfoPanel } from '../components/Panels'
import { PageHeader } from '../components/PageShell'
import { isDebugMode } from '../utils/debug'
import { isFixtureRecord, ProvenanceBlock } from '../components/ProvenanceBlock'

export function NaturalProductsPage() {
  const [queryTaxon, setQueryTaxon] = useState('')
  const [metabolite, setMetabolite] = useState('')
  const [method, setMethod] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null)
  const [result, setResult] = useState<NaturalProductLinkResponse | null>(null)

  async function runLinking() {
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
        setError({ message: '意外错误', detail: String(err) })
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    await runLinking()
  }

  return (
    <>
      <PageHeader title="天然产物关联" subtitle="按分类学距离与证据等级对候选化合物排序" />

      <InfoPanel>
        候选矩阵基于 bounded NPAtlas 快照与本地 fixture 记录。合成来源行会在结果中明确标记。
      </InfoPanel>

      <form className="card" onSubmit={handleSubmit}>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="query">查询分类单元</label>
            <input
              id="query"
              value={queryTaxon}
              onChange={(e) => setQueryTaxon(e.target.value)}
              placeholder="例如：Streptomyces"
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="metabolite">代谢物名称</label>
            <input id="metabolite" value={metabolite} onChange={(e) => setMetabolite(e.target.value)} placeholder="可选" />
          </div>
          <div className="form-group">
            <label htmlFor="method">观测方法</label>
            <input id="method" value={method} onChange={(e) => setMethod(e.target.value)} placeholder="例如：16S genus-level" />
          </div>
        </div>
        <button type="submit" className="btn" disabled={loading}>
          {loading ? '关联中…' : '关联候选化合物'}
        </button>
      </form>

      {loading && <p className="loading">正在构建候选矩阵…</p>}
      {error && <ErrorPanel message={error.message} detail={error.detail} onRetry={runLinking} />}

      {result && (
        <div className="card">
          <p className="muted-text" style={{ marginBottom: '1rem' }}>
            查询：{result.query_taxon}
            {result.metabolite_name && ` · 代谢物：${result.metabolite_name}`}
            {' · '}{result.rows.length} 个候选
          </p>

          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>排名</th>
                  <th>化合物</th>
                  <th>生产者</th>
                  <th>匹配</th>
                  <th>距离</th>
                  <th>等级</th>
                  <th>得分</th>
                  <th>状态</th>
                  <th>来源</th>
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
                      <td>{fixture ? <Badge label="合成" variant="fixture" /> : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {isDebugMode() && result.rows.map((row) => (
            <div key={`detail-${row.rank}`} className="card" style={{ marginTop: '1rem', fontSize: '0.875rem' }}>
              <strong>#{row.rank} {row.compound_name}</strong>
              <ProvenanceBlock data={row.provenance} />
            </div>
          ))}
        </div>
      )}
    </>
  )
}
