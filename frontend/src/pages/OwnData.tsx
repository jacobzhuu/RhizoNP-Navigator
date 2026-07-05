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
        setError({ message: '意外错误', detail: String(err) })
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
        <h1>自有数据工作区</h1>
        <p className="subtitle">组学关联 CSV → 分类学分级 → 候选关联</p>
      </header>

      <InfoPanel>
        MVP 不支持浏览器上传。可运行 <code>data/fixtures/own_data_demo</code> 演示数据，
        或在后端可读时指定本地目录路径。
      </InfoPanel>

      <form className="card" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="datadir">本地数据目录（可选）</label>
          <input
            id="datadir"
            value={dataDir}
            onChange={(e) => setDataDir(e.target.value)}
            placeholder="留空则使用演示 fixtures"
          />
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button type="button" className="btn" onClick={() => runPipeline(true)} disabled={loading}>
            运行演示数据
          </button>
          <button type="submit" className="btn btn-secondary" disabled={loading || !dataDir.trim()}>
            运行自定义目录
          </button>
        </div>
      </form>

      {loading && <p className="loading">正在运行流程…</p>}
      {error && <ErrorPanel message={error.message} detail={error.detail} />}

      {result && (
        <>
          <div className="card">
            已处理 <strong>{result.association_count}</strong> 条关联
            <ProvenanceBlock data={result.provenance} />
          </div>

          {associations.map((assoc, idx) => (
            <div key={assoc.association_id ?? idx} className="card">
              <h3>
                {assoc.source_raw_label} ↔ {assoc.target_raw_label}
              </h3>
              <div className="result-meta">
                <span>得分：{assoc.score?.toFixed(4) ?? '—'}</span>
                <span>校正 p 值：{assoc.adjusted_p?.toFixed(4) ?? '—'}</span>
                <span>方法：{assoc.method ?? '—'}</span>
              </div>

              {assoc.taxonomy_grading && (
                <div style={{ marginTop: '1rem' }}>
                  <h4 style={{ fontSize: '0.95rem' }}>分类学分级</h4>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
                    {assoc.taxonomy_grading.taxonomy_distance && (
                      <Badge label={assoc.taxonomy_grading.taxonomy_distance} variant="same-genus" />
                    )}
                    {assoc.taxonomy_grading.evidence_tier && (
                      <Badge label={`等级 ${assoc.taxonomy_grading.evidence_tier}`} variant={tierBadgeVariant(assoc.taxonomy_grading.evidence_tier)} />
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
                  <h4 style={{ fontSize: '0.95rem' }}>候选矩阵</h4>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>排名</th>
                        <th>化合物</th>
                        <th>生产者</th>
                        <th>匹配</th>
                        <th>等级</th>
                        <th>得分</th>
                        <th>状态</th>
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
              <h3>导出</h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                复制下方 JSON 用于 notebook 或报告。
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
