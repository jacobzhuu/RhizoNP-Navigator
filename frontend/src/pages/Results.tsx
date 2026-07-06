import { useCallback, type FormEvent } from 'react'
import { useResultsSession } from '../context/ResultsSessionContext'
import { HistorySavedNotice } from '../components/HistorySavedNotice'
import { IconChart, IconFlask, IconSparkles, IconTarget } from '../components/icons'
import { ErrorPanel } from '../components/Panels'
import { FeaturePage, PageHeader } from '../components/PageShell'
import { ResultsInterpretationView } from '../components/ResultsInterpretationView'
import { SectionCard } from '../components/SectionCard'
import { useHistoryUrlSync } from '../hooks/useHistoryUrlSync'

const STEPS = [
  { id: 1, label: '关联对象' },
  { id: 2, label: '统计证据' },
  { id: 3, label: '实验背景' },
  { id: 4, label: '证据解释' },
]

type ResultExample = {
  label: string
  hint: string
  taxon: string
  metabolite: string
  direction: string
  effectSize: string
  pValue: string
  method: string
}

/** Rotating demos that surface different RAG paths (literature, NP linking, taxonomy tiers, abstention). */
const RESULT_EXAMPLES: ResultExample[] = [
  {
    label: '属级观测 × 未知 LC-MS 特征',
    hint: '文献桥接召回根际上下文，同时约束属级观测不能升级为菌株生产结论。',
    taxon: 'Streptomyces',
    metabolite: 'Feature_M123',
    direction: 'positive',
    effectSize: '0.72',
    pValue: '0.003',
    method: '16S genus-level',
  },
  {
    label: '菌株级 × 已知化合物（强证据）',
    hint: '天然产物库直接匹配 Rapamycin，分类学距离为同菌株，适合展示证据支持路径。',
    taxon: 'Streptomyces hygroscopicus OS-2',
    metabolite: 'rapamycin',
    direction: 'positive',
    effectSize: '0.68',
    pValue: '0.004',
    method: 'strain-level genome',
  },
  {
    label: '属级观测 × 命名化合物',
    hint: 'NP 记录指向近缘菌株产物，系统只给出候选解释并阻止过度外推。',
    taxon: 'Streptomyces',
    metabolite: 'rapamycin',
    direction: 'positive',
    effectSize: '0.55',
    pValue: '0.018',
    method: '16S genus-level',
  },
  {
    label: '物种级 × 同种已知产物',
    hint: 'Avermectin 与 Streptomyces avermitilis 的结构化关联，展示物种级证据整合。',
    taxon: 'Streptomyces avermitilis',
    metabolite: 'avermectin',
    direction: 'positive',
    effectSize: '0.81',
    pValue: '0.001',
    method: '16S species-level',
  },
  {
    label: '分类不匹配 × 已知化合物',
    hint: 'Bacillus 与 Rapamycin 缺乏生产记录，系统应收敛为弱支持或证据不足。',
    taxon: 'Bacillus subtilis',
    metabolite: 'rapamycin',
    direction: 'positive',
    effectSize: '0.41',
    pValue: '0.021',
    method: '16S species-level',
  },
  {
    label: '未知分类 × 未知特征',
    hint: '无文献片段、无天然产物候选时，展示受约束写作与证据不足判断。',
    taxon: 'Pseudomonas fluorescens',
    metabolite: 'Feature_X999',
    direction: 'negative',
    effectSize: '-0.35',
    pValue: '0.04',
    method: 'shotgun metagenomics',
  },
]

function getStepFlowState({
  taxon,
  metabolite,
  direction,
  effectSize,
  pValue,
  method,
  hasResult,
}: {
  taxon: string
  metabolite: string
  direction: string
  effectSize: string
  pValue: string
  method: string
  hasResult: boolean
}) {
  const step1Done = Boolean(taxon.trim() && metabolite.trim())
  const step2Done = Boolean(
    direction &&
    effectSize.trim() !== '' &&
    Number.isFinite(Number(effectSize)) &&
    (pValue.trim() === '' || Number.isFinite(Number(pValue))),
  )
  const step3Done = Boolean(method.trim())

  let currentStep = 1
  if (hasResult) {
    currentStep = 4
  } else if (!step1Done) {
    currentStep = 1
  } else if (!step2Done) {
    currentStep = 2
  } else if (!step3Done) {
    currentStep = 3
  } else {
    currentStep = 4
  }

  return STEPS.map((step) => ({
    ...step,
    completed: hasResult || step.id < currentStep,
    active: !hasResult && step.id === currentStep,
    pending: !hasResult && step.id > currentStep,
    connectorDone: hasResult || step.id < currentStep,
  }))
}

function StepFlow(props: {
  taxon: string
  metabolite: string
  direction: string
  effectSize: string
  pValue: string
  method: string
  hasResult: boolean
}) {
  const steps = getStepFlowState(props)

  return (
    <nav className="step-flow" aria-label="解释流程">
      <ol className="step-flow-list">
        {steps.map((step) => {
          const itemClass = [
            'step-flow-item',
            step.completed && 'step-flow-item--completed',
            step.active && 'step-flow-item--active',
            step.pending && 'step-flow-item--pending',
            step.connectorDone && 'step-flow-item--connector-done',
          ].filter(Boolean).join(' ')

          return (
            <li
              key={step.id}
              className={itemClass}
              aria-current={step.active ? 'step' : undefined}
            >
              <span className="step-flow-dot" aria-hidden="true" />
              <span className="step-flow-label">{step.label}</span>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

export function ResultsPage() {
  const session = useResultsSession()
  const {
    taxon,
    metabolite,
    direction,
    effectSize,
    pValue,
    method,
    useLlm,
    exampleIndex,
    activeExampleIndex,
    loading,
    restoring,
    error,
    result,
    historyId,
    setTaxon,
    setMetabolite,
    setDirection,
    setEffectSize,
    setPValue,
    setMethod,
    setUseLlm,
    setExampleIndex,
    setActiveExampleIndex,
    interpretFinding,
    restoreFromHistory,
    clearResult,
  } = session

  const { clearHistoryParam } = useHistoryUrlSync({
    historyId,
    restoring,
    onRestore: restoreFromHistory,
  })

  const handleSubmit = useCallback(async (e: FormEvent) => {
    e.preventDefault()
    clearHistoryParam()
    await interpretFinding()
  }, [clearHistoryParam, interpretFinding])

  const handleRetry = useCallback(async () => {
    clearHistoryParam()
    await interpretFinding()
  }, [clearHistoryParam, interpretFinding])

  function fillExample() {
    const example = RESULT_EXAMPLES[exampleIndex]
    clearHistoryParam()
    clearResult()
    setTaxon(example.taxon)
    setMetabolite(example.metabolite)
    setDirection(example.direction)
    setEffectSize(example.effectSize)
    setPValue(example.pValue)
    setMethod(example.method)
    setActiveExampleIndex(exampleIndex)
    setExampleIndex((index) => (index + 1) % RESULT_EXAMPLES.length)
  }

  const invalidNumber = effectSize.trim() === '' || !Number.isFinite(Number(effectSize)) || (pValue.trim() !== '' && !Number.isFinite(Number(pValue)))
  const canSubmit = !loading && !restoring && !invalidNumber && Boolean(taxon.trim()) && Boolean(metabolite.trim()) && Boolean(method.trim())

  return (
    <FeaturePage className="results-page">
      <PageHeader
        icon={IconFlask}
        iconTheme="teal"
        title="结果解释"
        subtitle="将你的微生物–代谢物关联结果转化为有外部证据支持的科学解释"
      />

      <StepFlow
        taxon={taxon}
        metabolite={metabolite}
        direction={direction}
        effectSize={effectSize}
        pValue={pValue}
        method={method}
        hasResult={Boolean(result)}
      />

      <form id="results-form" className="feature-form-stack" onSubmit={handleSubmit}>
        <SectionCard
          icon={IconTarget}
          iconTheme="blue"
          title="关联对象"
          description="定义需要解释的微生物分类单元与代谢物或特征。"
        >
          <div className="entity-relation">
            <div className="entity-relation-field">
              <div className="form-field">
                <input
                  id="result-taxon"
                  value={taxon}
                  onChange={(e) => setTaxon(e.target.value)}
                  placeholder="Streptomyces"
                  required
                  aria-label="Taxon"
                />
              </div>
              <span className="entity-relation-label">Taxon</span>
            </div>
            <span className="entity-relation-connector" aria-hidden="true">↔</span>
            <div className="entity-relation-field">
              <div className="form-field">
                <input
                  id="result-metabolite"
                  value={metabolite}
                  onChange={(e) => setMetabolite(e.target.value)}
                  placeholder="M1023"
                  required
                  aria-label="Metabolite / Feature"
                />
              </div>
              <span className="entity-relation-label">Metabolite / Feature</span>
            </div>
          </div>
        </SectionCard>

        <SectionCard
          icon={IconChart}
          iconTheme="green"
          title="统计证据"
          description="描述关联方向、效应强度与显著性，用于判断证据支持程度。"
        >
          <div className="stats-evidence-row">
            <div className="form-field">
              <label htmlFor="result-direction">关联方向</label>
              <select id="result-direction" value={direction} onChange={(e) => setDirection(e.target.value)}>
                <option value="positive">↑ 正相关</option>
                <option value="negative">↓ 负相关</option>
                <option value="unknown">未知</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="result-effect">Effect size / r</label>
              <input
                id="result-effect"
                value={effectSize}
                onChange={(e) => setEffectSize(e.target.value)}
                inputMode="decimal"
                placeholder="0.72"
                required
              />
            </div>
            <div className="form-field">
              <label htmlFor="result-p">P value</label>
              <input
                id="result-p"
                value={pValue}
                onChange={(e) => setPValue(e.target.value)}
                inputMode="decimal"
                placeholder="0.003"
              />
            </div>
          </div>
        </SectionCard>

        <SectionCard
          icon={IconFlask}
          iconTheme="teal"
          title="实验背景"
          description="描述观测或分析方法，帮助系统判断证据适用边界。"
        >
          <div className="form-field form-field--full">
            <label htmlFor="result-method">Observation method</label>
            <input
              id="result-method"
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              placeholder="例如 16S genus-level"
              required
            />
          </div>
        </SectionCard>

        <div className="card submit-area">
          <div className="interpretation-mode">
            <span className="interpretation-mode-label">解释模式</span>
            <label className="toggle-switch" htmlFor="results-use-llm">
              <input
                id="results-use-llm"
                type="checkbox"
                checked={useLlm}
                onChange={(e) => setUseLlm(e.target.checked)}
              />
              <span className="toggle-switch-track" aria-hidden="true" />
              <span>LLM 增强</span>
            </label>
            <p className="interpretation-mode-hint">
              结合受约束的大模型生成能力组织证据解释；关闭时使用规则化写作流程。
            </p>
          </div>
          <div className="submit-area-actions">
            <button type="submit" className="btn btn-teal" disabled={!canSubmit} aria-busy={loading}>
              <IconSparkles size={18} />
              {loading ? '解释中…' : '生成科学解释'}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={fillExample}
              disabled={loading || restoring}
              aria-label={`填入示例值：${RESULT_EXAMPLES[exampleIndex].label}`}
            >
              填入示例值
            </button>
          </div>
          {activeExampleIndex !== null && (
            <p className="interpretation-mode-hint example-scenario-hint">
              当前示例（{activeExampleIndex + 1}/{RESULT_EXAMPLES.length}）：
              <strong>{RESULT_EXAMPLES[activeExampleIndex].label}</strong>
              — {RESULT_EXAMPLES[activeExampleIndex].hint}
              {' '}再次点击可切换至「{RESULT_EXAMPLES[exampleIndex].label}」。
            </p>
          )}
        </div>
      </form>

      {restoring && <p className="loading">加载历史记录…</p>}
      {loading && <p className="loading">正在运行分类学分级、天然产物关联、文献桥接和证据写作…</p>}
      {error && <ErrorPanel message={error.message} detail={error.detail} onRetry={handleRetry} />}

      {result && !restoring && (
        <div className="results-output">
          {result.history_id && <HistorySavedNotice historyId={result.history_id} />}
          <ResultsInterpretationView result={result} />
        </div>
      )}
    </FeaturePage>
  )
}
