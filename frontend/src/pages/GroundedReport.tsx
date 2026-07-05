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
  question: '现有证据支持哪些保守结论？',
  evidence_items: [
    {
      evidence_id: '00000000-0000-4000-8000-000000000001',
      claim_type: 'association',
      predicate: 'correlates_with',
      object_literal: 'Feature_M123',
      evidence_tier: 'same_genus',
      directness: 'indirect',
      confidence: 0.6,
      supporting_span: '仅属级相关，不能支持菌株水平生产主张。',
      provenance: { fixture: true },
    },
  ],
  taxonomy_warnings: ['属级 16S 观测不能支持菌株水平生产主张。'],
  limitations: ['相关不等于因果。'],
  use_llm: true,
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
        setError({ message: 'JSON 格式无效', detail: err.message })
      } else if (err instanceof BackendUnavailableError || err instanceof ApiError) {
        setError({ message: err.message, detail: err instanceof ApiError ? err.detail : undefined })
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
        <h1>证据报告</h1>
        <p className="subtitle">有证据边界约束的科学回答，含主张溯源</p>
      </header>

      <InfoPanel>
        默认启用 DeepSeek 写作器（<code>use_llm: true</code>），需本地 <code>.env</code> 已配置{' '}
        <code>DEEPSEEK_API_KEY</code>。未配置或门控失败时自动回退确定性写作器。
      </InfoPanel>

      <form className="card" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="json">请求 JSON</label>
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
            {loading ? '生成中…' : '生成报告'}
          </button>
          <button type="button" className="btn btn-secondary" onClick={loadDemo}>
            加载演示示例
          </button>
        </div>
      </form>

      {loading && <p className="loading">正在生成证据约束回答…</p>}
      {error && <ErrorPanel message={error.message} detail={error.detail} />}

      {result && (
        <div className="card">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
            <Badge label={result.status} variant={statusVariant(result.status)} />
            <Badge label={`写作器：${result.writer_mode}`} variant="mode" />
          </div>

          <h3>回答</h3>
          <p>{result.answer}</p>

          {result.claims.length > 0 && (
            <>
              <h3>主张</h3>
              <ul>
                {result.claims.map((claim, i) => (
                  <li key={i} style={{ marginBottom: '0.5rem' }}>
                    <Badge label={claim.claim_level} variant={tierBadgeVariant(claim.claim_level)} />
                    {' '}{claim.text}
                    <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: '0.25rem' }}>
                      证据引用：{claim.evidence_refs.join(', ')}
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}

          {result.evidence_refs.length > 0 && (
            <p style={{ fontSize: '0.875rem' }}>
              <strong>证据引用：</strong> {result.evidence_refs.join(', ')}
            </p>
          )}

          <WarningPanel title="分类学警告" items={lastWarnings} />
          <LimitationsPanel items={result.limitations} />

          {result.suggested_validations.length > 0 && (
            <>
              <h3>建议验证</h3>
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
