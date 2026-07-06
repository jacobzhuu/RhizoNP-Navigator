import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { type CorpusSummaryResponse } from '../api/types'
import { useAskSession } from '../context/AskSessionContext'
import { AskResultView } from '../components/AskResultView'
import { HistorySavedNotice } from '../components/HistorySavedNotice'
import { IconDatabase, IconDocument, IconLayers, IconMessage, IconSettings, IconShieldCheck, IconSparkles } from '../components/icons'
import { LoadingSteps } from '../components/LoadingSteps'
import { ErrorPanel, InfoPanel } from '../components/Panels'
import { FeaturePage, PageHeader } from '../components/PageShell'
import { SectionCard } from '../components/SectionCard'
import { useHistoryUrlSync } from '../hooks/useHistoryUrlSync'

const EXAMPLE_QUESTIONS = [
  'Streptomyces sp. SANK 62799 是否有 A-503083 F 生产记录？',
  '检测到 Streptomyces 是否说明样本中存在天然产物生产证据？',
  '根损伤样本中的 Streptomyces 与 Feature_M123 有哪些候选线索？',
  'Bacillus 是否有天然产物生产证据？',
]

const RETRIEVAL_MODE_OPTIONS = [
  { value: 'hybrid_rerank', label: '综合检索（推荐）' },
  { value: 'hybrid', label: '混合检索' },
  { value: 'dense', label: '语义检索' },
  { value: 'bm25', label: '关键词检索' },
]

export function AskPage() {
  const session = useAskSession()
  const {
    question,
    retrievalMode,
    topK,
    maxQueries,
    useLlm,
    showAdvanced,
    loading,
    loadingStep,
    restoring,
    error,
    result,
    historyId,
    setQuestion,
    setRetrievalMode,
    setTopK,
    setMaxQueries,
    setUseLlm,
    setShowAdvanced,
    submitQuestion,
    restoreFromHistory,
  } = session

  const [corpus, setCorpus] = useState<CorpusSummaryResponse | null>(null)
  const [corpusError, setCorpusError] = useState<string | null>(null)

  const { clearHistoryParam } = useHistoryUrlSync({
    historyId,
    restoring,
    onRestore: restoreFromHistory,
  })

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

  const handleSubmit = useCallback(async (e: FormEvent) => {
    e.preventDefault()
    clearHistoryParam()
    await submitQuestion()
  }, [clearHistoryParam, submitQuestion])

  const handleRetry = useCallback(async () => {
    clearHistoryParam()
    await submitQuestion()
  }, [clearHistoryParam, submitQuestion])

  return (
    <FeaturePage>
      <PageHeader
        icon={IconMessage}
        iconTheme="blue"
        title="科研问答"
        subtitle="输入你的科研问题，获取带证据来源与边界说明的回答"
      />

      <form onSubmit={handleSubmit}>
        <SectionCard
          className="core-input-card"
          icon={IconMessage}
          iconTheme="blue"
          title="问题输入"
          description="描述你的科研问题，或使用下方示例快速开始。"
        >
          <div className="form-field form-field--full">
            <label htmlFor="question">科研问题</label>
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

          <div className="core-form-actions">
            <button
              type="submit"
              className="btn btn-primary-cta"
              disabled={loading || restoring || question.trim().length < 3}
              aria-busy={loading}
            >
              <IconSparkles size={18} />
              {loading ? '分析中…' : '分析并回答'}
            </button>
            <button
              type="button"
              className={`btn btn-ghost advanced-toggle-btn${showAdvanced ? ' active' : ''}`}
              aria-expanded={showAdvanced}
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              <IconSettings size={16} />
              高级检索设置
            </button>
          </div>
        </SectionCard>

        {showAdvanced && (
          <SectionCard
            className="advanced-settings-panel"
            icon={IconSettings}
            iconTheme="slate"
            title="高级检索设置"
            description="调整召回模式、证据数量与写作方式。默认设置适用于大多数科研问题。"
          >
            <div className="form-grid">
              <div className="form-field form-field--full">
                <label htmlFor="retrieval-mode">召回模式</label>
                <select id="retrieval-mode" value={retrievalMode} onChange={(e) => setRetrievalMode(e.target.value)}>
                  {RETRIEVAL_MODE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-field form-field--half">
                <label htmlFor="top-k">证据 TOP-K</label>
                <input id="top-k" type="number" min={1} max={20} value={topK} onChange={(e) => setTopK(Number(e.target.value))} />
              </div>
              <div className="form-field form-field--half">
                <label htmlFor="max-queries">扩展查询数</label>
                <input id="max-queries" type="number" min={1} max={5} value={maxQueries} onChange={(e) => setMaxQueries(Number(e.target.value))} />
              </div>
              <div className="form-field form-field--full">
                <label className="checkbox-label" htmlFor="use-llm">
                  <input id="use-llm" type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} />
                  写作模式：尝试大模型回答（无 API Key 时回退规则写作）
                </label>
              </div>
            </div>
          </SectionCard>
        )}
      </form>

      {corpusError && (
        <InfoPanel>
          <strong>语料状态</strong>
          <p style={{ margin: '0.35rem 0 0' }}>{corpusError}</p>
        </InfoPanel>
      )}

      {corpus && (
        <section className="card evidence-coverage">
          <p className="evidence-coverage-title">当前可召回证据库</p>
          <div className="evidence-coverage-stats">
            <div className="evidence-coverage-stat">
              <span className="evidence-coverage-stat-icon"><IconDocument size={16} /></span>
              <span><strong>{corpus.paper_count}</strong> 文献</span>
            </div>
            <div className="evidence-coverage-stat">
              <span className="evidence-coverage-stat-icon"><IconLayers size={16} /></span>
              <span><strong>{corpus.paper_chunk_count}</strong> 文本片段</span>
            </div>
            <div className="evidence-coverage-stat">
              <span className="evidence-coverage-stat-icon"><IconShieldCheck size={16} /></span>
              <span><strong>{corpus.real_chunk_count}</strong> 真实片段</span>
            </div>
          </div>
          {corpus.top_taxa.length > 0 && (
            <div className="evidence-coverage-taxa">
              <div className="evidence-coverage-stat">
                <span className="evidence-coverage-stat-icon"><IconDatabase size={16} /></span>
                <span>
                  主要菌属：{corpus.top_taxa.slice(0, 5).map((item) => item.value).join('、')}
                </span>
              </div>
            </div>
          )}
        </section>
      )}

      {restoring && <p className="loading">加载历史记录…</p>}
      {loading && <LoadingSteps activeStep={loadingStep} />}
      {error && <ErrorPanel message={error.message} detail={error.detail} onRetry={handleRetry} />}

      {result && !restoring && (
        <>
          {result.history_id && <HistorySavedNotice historyId={result.history_id} />}
          <AskResultView result={result} useLlm={useLlm} />
        </>
      )}
    </FeaturePage>
  )
}
