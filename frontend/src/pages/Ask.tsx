import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { ApiError, BackendUnavailableError, type AskResponse, type CorpusSummaryResponse } from '../api/types'
import { Badge } from '../components/Badge'
import { EvidenceCard } from '../components/EvidenceCard'
import { LoadingSteps } from '../components/LoadingSteps'
import { ErrorPanel, InfoPanel, LimitationsPanel, WarningPanel } from '../components/Panels'
import { PageHeader } from '../components/PageShell'
import { ProvenanceBlock } from '../components/ProvenanceBlock'
import { isDebugMode } from '../utils/debug'

const EXAMPLE_QUESTIONS = [
  '检测到 Streptomyces 是否说明样本中存在天然产物生产证据？',
  '根际 Streptomyces 与 polyketide 相关的文献证据有哪些？',
  '属级 16S 信号能否支持菌株水平产物生产结论？',
  'plant–microbe rhizosphere natural product biosynthesis evidence',
]

const RETRIEVAL_MODES = ['bm25', 'dense', 'hybrid', 'hybrid_rerank']

function statusVariant(status: string): 'supported' | 'partial' | 'insufficient' | 'mode' {
  if (status === 'SUPPORTED') return 'supported'
  if (status === 'PARTIALLY_SUPPORTED') return 'partial'
  if (status === 'INSUFFICIENT_EVIDENCE' || status === 'CONFLICTING_EVIDENCE') return 'insufficient'
  return 'mode'
}

function statusLabel(status: string): string {
  if (status === 'SUPPORTED') return '证据支持'
  if (status === 'PARTIALLY_SUPPORTED') return '部分支持'
  if (status === 'INSUFFICIENT_EVIDENCE') return '证据不足'
  if (status === 'CONFLICTING_EVIDENCE') return '证据冲突'
  return status
}

function writerModeLabel(mode: string): string {
  if (mode === 'deepseek_applied') return 'LLM 证据写作'
  if (mode === 'fallback_after_citation_failure') return '引用校验保护模式'
  if (mode === 'fallback_after_constraint_violation') return '科学约束保护模式'
  if (mode === 'fallback_after_schema_failure') return '结构校验保护模式'
  if (mode === 'fallback_after_provider_error') return '模型服务回退模式'
  if (mode === 'deterministic_offline') return '离线证据写作'
  if (mode === 'fallback') return '规则化证据写作'
  return mode
}

function selectedLimitations(items: string[]): string[] {
  const preferred = items.filter((item) =>
    item.includes('不能替代实验验证') ||
    item.includes('共现不等同于') ||
    item.includes('菌株水平') ||
    item.includes('fixture') ||
    item.includes('候选证据') ||
    item.includes('证据边界') ||
    item.includes('RAG')
  )
  return (preferred.length ? preferred : items).slice(0, 4)
}

export function AskPage() {
  const [question, setQuestion] = useState('')
  const [retrievalMode, setRetrievalMode] = useState('hybrid_rerank')
  const [topK, setTopK] = useState(5)
  const [maxQueries, setMaxQueries] = useState(3)
  const [useLlm, setUseLlm] = useState(true)
  const [loading, setLoading] = useState(false)
  const [loadingStep, setLoadingStep] = useState(0)
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null)
  const [result, setResult] = useState<AskResponse | null>(null)
  const [corpus, setCorpus] = useState<CorpusSummaryResponse | null>(null)
  const [corpusError, setCorpusError] = useState<string | null>(null)
  const stepTimerRef = useRef<number | null>(null)

  useEffect(() => {
    let active = true
    api.getCorpusSummary()
      .then((data) => {
        if (active) {
          setCorpus(data)
          setCorpusError(null)
        }
      })
      .catch(() => {
        if (active) {
          setCorpus(null)
          setCorpusError('无法加载文献语料摘要，请确认数据库已启动并完成 ingest。')
        }
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!loading) {
      if (stepTimerRef.current != null) {
        window.clearInterval(stepTimerRef.current)
        stepTimerRef.current = null
      }
      return
    }
    setLoadingStep(0)
    stepTimerRef.current = window.setInterval(() => {
      setLoadingStep((prev) => (prev < 3 ? prev + 1 : prev))
    }, 1200)
    return () => {
      if (stepTimerRef.current != null) {
        window.clearInterval(stepTimerRef.current)
        stepTimerRef.current = null
      }
    }
  }, [loading])

  async function submitQuestion() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.ask({
        question,
        retrieval_mode: retrievalMode,
        top_k: topK,
        max_queries: maxQueries,
        use_llm: useLlm,
      })
      setLoadingStep(3)
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
    await submitQuestion()
  }

  return (
    <>
      <PageHeader
        title="科研问答"
        subtitle="输入科学问题，系统将规划检索、召回文献证据并生成有边界约束的回答"
      />

      <form className="card" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="question">问题</label>
          <textarea
            id="question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={4}
            placeholder="例如：根际 Streptomyces 与天然产物相关的证据有哪些？"
            required
            minLength={3}
          />
        </div>

        <div className="example-chips" aria-label="示例问题">
          {EXAMPLE_QUESTIONS.map((example) => (
            <button
              key={example}
              type="button"
              className="example-chip"
              onClick={() => setQuestion(example)}
            >
              {example}
            </button>
          ))}
        </div>

        <details className="advanced-settings">
          <summary>高级设置</summary>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="retrieval-mode">召回模式</label>
              <select id="retrieval-mode" value={retrievalMode} onChange={(e) => setRetrievalMode(e.target.value)}>
                {RETRIEVAL_MODES.map((mode) => (
                  <option key={mode} value={mode}>{mode}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label htmlFor="top-k">证据 Top-K</label>
              <input id="top-k" type="number" min={1} max={20} value={topK} onChange={(e) => setTopK(Number(e.target.value))} />
            </div>
            <div className="form-group">
              <label htmlFor="max-queries">扩展查询数</label>
              <input id="max-queries" type="number" min={1} max={5} value={maxQueries} onChange={(e) => setMaxQueries(Number(e.target.value))} />
            </div>
            <div className="form-group">
              <span className="form-label">写作模式</span>
              <label className="checkbox-label" htmlFor="use-llm">
                <input id="use-llm" type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} />
                启用大模型写作
              </label>
            </div>
          </div>
        </details>

        <button type="submit" className="btn" disabled={loading || question.trim().length < 3} aria-busy={loading}>
          {loading ? '分析中…' : '分析并回答'}
        </button>
      </form>

      {corpusError && (
        <InfoPanel>
          <strong>语料状态</strong>
          <p style={{ margin: '0.35rem 0 0' }}>{corpusError}</p>
        </InfoPanel>
      )}

      {corpus && (
        <details className="card corpus-summary">
          <summary>
            当前可召回库：{corpus.paper_count} 篇文献 · {corpus.real_chunk_count} 条真实片段
            {corpus.top_taxa.length > 0 && (
              <> · 主要菌属 {corpus.top_taxa.slice(0, 5).map((item) => item.value).join('、')}</>
            )}
          </summary>
          <div className="summary-grid">
            <div>
              <strong>{corpus.paper_count}</strong>
              <span>文献</span>
            </div>
            <div>
              <strong>{corpus.paper_chunk_count}</strong>
              <span>片段</span>
            </div>
            <div>
              <strong>{corpus.real_chunk_count}</strong>
              <span>真实片段</span>
            </div>
          </div>
          {corpus.top_taxa.length > 0 && (
            <div className="matched-terms">
              {corpus.top_taxa.slice(0, 8).map((item) => (
                <span key={`taxa-${item.value}`} className="matched-term">{item.value}: {item.count}</span>
              ))}
            </div>
          )}
        </details>
      )}

      {loading && <LoadingSteps activeStep={loadingStep} />}
      {error && <ErrorPanel message={error.message} detail={error.detail} onRetry={submitQuestion} />}

      {result && (
        <>
          <section className="card">
            <h3>最终回答</h3>
            <div className="badge-row">
              <Badge label={statusLabel(result.answer.status)} variant={statusVariant(result.answer.status)} />
              <Badge label={writerModeLabel(result.answer.writer_mode)} variant="mode" />
            </div>
            <p className="answer-lead">{result.answer.answer}</p>

            {result.answer.claims.length > 0 && (
              <>
                <h3>依据</h3>
                <ul className="evidence-list">
                  {result.answer.claims.map((claim, index) => (
                    <li key={index}>{claim.text}</li>
                  ))}
                </ul>
              </>
            )}
            <LimitationsPanel items={selectedLimitations(result.answer.limitations)} />
            {result.answer.suggested_validations.length > 0 && (
              <>
                <h3>下一步验证</h3>
                <ul>
                  {result.answer.suggested_validations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </>
            )}
          </section>

          <section className="card">
            <h3>检索与推理过程</h3>
            <div className="badge-row">
              <Badge label={`意图：${result.question_plan.intent}`} variant="mode" />
              <Badge label={`召回：${result.retrieval_mode}`} variant="mode" />
            </div>

            <h3>问题理解</h3>
            <div className="result-meta">
              {Object.entries(result.question_plan.entities).map(([key, values]) => (
                <span key={key}>{key}：{values.length ? values.join(', ') : '—'}</span>
              ))}
            </div>
            <WarningPanel title="证据边界警告" items={result.question_plan.warnings} />

            <h3>同义词与查询扩展</h3>
            {Object.keys(result.question_plan.synonym_expansions).length > 0 ? (
              <div className="matched-terms">
                {Object.entries(result.question_plan.synonym_expansions).map(([key, values]) => (
                  <span key={key} className="matched-term">{key}: {values.join(' / ')}</span>
                ))}
              </div>
            ) : (
              <p className="muted-text">未识别到需要领域同义词扩展的实体。</p>
            )}
            <ol>
              {result.question_plan.planned_queries.map((query) => (
                <li key={`${query.query_type}-${query.query_text}`} className="planned-query-item">
                  <strong>{query.query_text}</strong>
                  <div className="muted-text">
                    {query.query_type} · {query.rationale}
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <section className="card">
            <h3>召回证据</h3>
            <p className="muted-text">
              共合并 {result.retrieval_hits.length} 条文献片段。
            </p>
            {result.retrieval_hits.length === 0 && (
              <WarningPanel
                title="未召回到文献证据"
                items={[
                  '当前问题没有命中可召回的 paper_chunks。',
                  '最终回答会进入证据不足状态，不会编造引用或结论。',
                ]}
              />
            )}
            {result.retrieval_hits.map((hit, index) => (
              <EvidenceCard key={hit.chunk_id} hit={hit} index={index} />
            ))}
          </section>

          {isDebugMode() && (
            <section className="card">
              <details>
                <summary>开发审计信息</summary>
                <p className="muted-text">
                  原始写作模式：{result.answer.writer_mode}。引用校验、faithfulness 诊断和完整溯源保留给开发审计。
                </p>
                <ProvenanceBlock data={result.answer.provenance} defaultOpen={false} />
                <ProvenanceBlock data={result.provenance} defaultOpen={false} />
              </details>
            </section>
          )}
        </>
      )}
    </>
  )
}
