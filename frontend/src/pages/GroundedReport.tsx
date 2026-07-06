import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import {
  ApiError,
  BackendUnavailableError,
  type GroundedAnswerRequest,
  type GroundedAnswerResponse,
} from '../api/types'
import { Badge, tierBadgeVariant } from '../components/Badge'
import { AnswerText } from '../components/AnswerText'
import { ErrorPanel, InfoPanel, LimitationsPanel, WarningPanel } from '../components/Panels'
import { PageHeader } from '../components/PageShell'
import { ProvenanceBlock } from '../components/ProvenanceBlock'
import { isDebugMode } from '../utils/debug'

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
  const debug = isDebugMode()
  const [question, setQuestion] = useState('')
  const [useLlm, setUseLlm] = useState(true)
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

  async function generateReport() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const body = debug
        ? (JSON.parse(jsonInput) as GroundedAnswerRequest)
        : ({
            question,
            evidence_items: [],
            use_llm: useLlm,
          } satisfies GroundedAnswerRequest)
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

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    await generateReport()
  }

  return (
    <>
      <PageHeader title="证据报告" subtitle="有证据边界约束的科学回答，含主张溯源" />

      <InfoPanel>
        可选启用大模型写作（需配置 <code>DEEPSEEK_API_KEY</code>）。校验失败或未配置时自动回退确定性写作器。
      </InfoPanel>

      <form className="card" onSubmit={handleSubmit}>
        {debug ? (
          <div className="form-group">
            <label htmlFor="json">请求 JSON（调试模式）</label>
            <textarea
              id="json"
              value={jsonInput}
              onChange={(e) => setJsonInput(e.target.value)}
              rows={14}
              style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}
            />
          </div>
        ) : (
          <>
            <div className="form-group">
              <label htmlFor="question">问题</label>
              <textarea
                id="question"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={4}
                placeholder="输入需要生成证据约束回答的问题"
                required
              />
            </div>
            <div className="form-group">
              <label className="checkbox-label" htmlFor="grounded-use-llm">
                <input
                  id="grounded-use-llm"
                  type="checkbox"
                  checked={useLlm}
                  onChange={(e) => setUseLlm(e.target.checked)}
                />
                启用大模型写作
              </label>
            </div>
          </>
        )}
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button type="submit" className="btn" disabled={loading}>
            {loading ? '生成中…' : '生成报告'}
          </button>
          {debug && (
            <button type="button" className="btn btn-secondary" onClick={loadDemo}>
              加载演示示例
            </button>
          )}
        </div>
      </form>

      {loading && <p className="loading">正在生成证据约束回答…</p>}
      {error && <ErrorPanel message={error.message} detail={error.detail} onRetry={generateReport} />}

      {result && (
        <div className="card">
          <div className="badge-row">
            <Badge label={result.status} variant={statusVariant(result.status)} />
            <Badge label={`写作器：${result.writer_mode}`} variant="mode" />
          </div>

          <h3>回答</h3>
          <AnswerText text={result.answer} className="answer-lead" />

          {result.claims.length > 0 && (
            <>
              <h3>主张</h3>
              <ul>
                {result.claims.map((claim, i) => (
                  <li key={i} style={{ marginBottom: '0.5rem' }}>
                    <Badge label={claim.claim_level} variant={tierBadgeVariant(claim.claim_level)} />
                    {' '}{claim.text}
                  </li>
                ))}
              </ul>
            </>
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

          {debug && <ProvenanceBlock data={result.provenance} />}
        </div>
      )}
    </>
  )
}
