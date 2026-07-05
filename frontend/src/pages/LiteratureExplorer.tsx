import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { ApiError, BackendUnavailableError, type SearchResponse } from '../api/types'
import { Badge } from '../components/Badge'
import { ErrorPanel, InfoPanel } from '../components/Panels'
import { ProvenanceBlock } from '../components/ProvenanceBlock'

const RETRIEVAL_MODES = ['bm25', 'dense', 'hybrid', 'hybrid_rerank']

const DEMO_QUERY = 'Streptomyces Feature_M123'

export function LiteratureExplorerPage() {
  const [query, setQuery] = useState(DEMO_QUERY)
  const [mode, setMode] = useState('bm25')
  const [topK, setTopK] = useState(5)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<{ message: string; detail?: string; dbUnavailable?: boolean } | null>(null)
  const [response, setResponse] = useState<SearchResponse | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResponse(null)
    try {
      const result = await api.searchLiterature({
        query,
        top_k: topK,
        retrieval_mode: mode,
        filters: {
          sections: ['results'],
          source_types: ['paper'],
          dois: ['10.0000/rhizonp.fixture.lit.001'],
          journals: ['fixture'],
          taxa: ['Streptomyces'],
          compounds: ['FixturePolyketide-A'],
          host: ['Synthetic plant'],
        },
      })
      setResponse(result)
    } catch (err) {
      if (err instanceof BackendUnavailableError) {
        setError({ message: err.message, dbUnavailable: true })
      } else if (err instanceof ApiError) {
        const dbUnavailable = err.status >= 500 || err.detail?.includes('database') || err.detail?.includes('connection')
        setError({ message: err.message, detail: err.detail, dbUnavailable })
      } else {
        setError({ message: '意外错误', detail: String(err) })
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <header className="page-header">
        <h1>文献检索</h1>
        <p className="subtitle">检索已索引文献片段，并展示溯源轨迹</p>
      </header>

      <div className="panel-info">
        需要 PostgreSQL 并加载 Phase 2 文献 fixtures（
        <code>./scripts/start.sh db</code>）。当前仅使用合成 fixture 语料。
      </div>

      <form className="card" onSubmit={handleSubmit}>
        <div className="form-row">
          <div className="form-group" style={{ flex: 3 }}>
            <label htmlFor="query">查询</label>
            <input id="query" value={query} onChange={(e) => setQuery(e.target.value)} required />
          </div>
          <div className="form-group">
            <label htmlFor="mode">检索模式</label>
            <select id="mode" value={mode} onChange={(e) => setMode(e.target.value)}>
              {RETRIEVAL_MODES.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="topk">Top-K</label>
            <input id="topk" type="number" min={1} max={50} value={topK} onChange={(e) => setTopK(Number(e.target.value))} />
          </div>
        </div>
        <button type="submit" className="btn" disabled={loading}>
          {loading ? '检索中…' : '检索文献'}
        </button>
      </form>

      {loading && <p className="loading">正在检索文献片段…</p>}

      {error && (
        <>
          <ErrorPanel message={error.message} detail={error.detail} />
          {error.dbUnavailable && (
            <InfoPanel>
              <strong>数据库不可用</strong>
              <p style={{ margin: '0.35rem 0 0' }}>
                请先加载 fixtures：<code>./scripts/start.sh db</code>，再运行{' '}
                <code>make start-api</code>。无数据库端点（分级、关联、自有数据、报告）
                仍可正常使用。
              </p>
            </InfoPanel>
          )}
        </>
      )}

      {response && (
        <div>
          <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
            运行 {response.run_id.slice(0, 8)}… · 模式：{response.retrieval_mode} · {response.results.length} 条结果
          </p>
          {response.results.length === 0 && (
            <InfoPanel>查询与 fixture 过滤器未匹配到任何结果。</InfoPanel>
          )}
          {response.results.map((result) => (
            <div key={result.rank} className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
                <strong>排名 #{result.rank}</strong>
                <Badge label={`得分 ${result.score.toFixed(4)}`} variant="mode" />
              </div>
              <div className="result-meta">
                <span>DOI：{result.trace.doi ?? '—'}</span>
                <span>PMID：—（API 溯源中未返回）</span>
                <span>期刊：fixture</span>
                <span>年份：2026（fixture）</span>
                <span>章节：{result.trace.section}</span>
              </div>
              <p className="result-text">{result.text}</p>
              {result.matched_terms.length > 0 && (
                <div className="matched-terms">
                  {result.matched_terms.map((term) => (
                    <span key={term} className="matched-term">{term}</span>
                  ))}
                </div>
              )}
              <ProvenanceBlock
                data={{
                  chunk_id: result.trace.chunk_id,
                  paper_id: result.trace.paper_id,
                  doi: result.trace.doi,
                  source_url: result.trace.source_url,
                  section: result.trace.section,
                  char_start: result.trace.char_start,
                  char_end: result.trace.char_end,
                  score_components: result.score_components,
                }}
              />
            </div>
          ))}
        </div>
      )}
    </>
  )
}
