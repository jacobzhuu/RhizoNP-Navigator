import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import {
  ApiError,
  BackendUnavailableError,
  type ResultInterpretation,
  type ResultsInterpretationResponse,
} from '../api/types'
import { Badge } from '../components/Badge'
import { ErrorPanel } from '../components/Panels'
import { PageHeader } from '../components/PageShell'
import { ProvenanceBlock } from '../components/ProvenanceBlock'
import { isDebugMode } from '../utils/debug'

function statusVariant(status: string): 'supported' | 'partial' | 'insufficient' | 'mode' {
  if (status === 'SUPPORTED') return 'supported'
  if (status === 'PARTIALLY_SUPPORTED') return 'partial'
  if (status === 'INSUFFICIENT_EVIDENCE' || status === 'CONFLICTING_EVIDENCE') return 'insufficient'
  return 'mode'
}

function asRecords(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null) : []
}

function valueText(value: unknown, fallback = '—'): string {
  if (value == null || value === '') return fallback
  if (typeof value === 'number') return Number.isFinite(value) ? value.toString() : fallback
  return String(value)
}

function recordGroups(records: Record<string, unknown>) {
  return [
    { title: 'direct match', rows: asRecords(records.direct_match) },
    { title: 'same species', rows: asRecords(records.same_species) },
    { title: 'same genus', rows: asRecords(records.same_genus) },
    { title: 'indirect candidates', rows: asRecords(records.indirect_candidates) },
  ].filter((group) => group.rows.length > 0)
}

function ResultInterpretationCard({ item }: { item: ResultInterpretation }) {
  const literature = item.literature_evidence
  const literatureItems = asRecords(literature.items)
  const npRecords = item.natural_product_records
  const groups = recordGroups(npRecords)

  return (
    <article className="card interpretation-card">
      <section className="interpretation-section">
        <h3>你的发现</h3>
        <p className="answer-lead">{valueText(item.finding.text)}</p>
      </section>

      <section className="interpretation-section">
        <h3>系统判断</h3>
        <div className="badge-row">
          <Badge label={item.status_label} variant={statusVariant(item.status)} />
          <Badge label={item.status} variant="mode" />
        </div>
      </section>

      <section className="interpretation-grid">
        <div>
          <h3>当前证据支持什么</h3>
          <p>{item.supported_interpretation}</p>
        </div>
        <div>
          <h3>当前证据不能支持什么</h3>
          <p>{item.unsupported_interpretation}</p>
        </div>
      </section>

      <section className="interpretation-section">
        <h3>为什么这样判断</h3>
        <ol className="reasoning-list">
          {item.reasoning.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </section>

      <section className="interpretation-section">
        <h3>相关文献证据</h3>
        <p className="muted-text">
          相关文献 {valueText(literature.count, '0')} 条 · 直接/近分类证据 {valueText(literature.direct_count, '0')} 条 ·
          间接证据 {valueText(literature.indirect_count, '0')} 条
        </p>
        {literatureItems.length === 0 ? (
          <p className="muted-text">当前没有召回可展示的文献片段。</p>
        ) : (
          <div className="evidence-mini-list">
            {literatureItems.slice(0, 4).map((hit, index) => (
              <div key={`${valueText(hit.doi)}-${index}`} className="evidence-mini-item">
                <strong>{valueText(hit.title, `文献 ${index + 1}`)}</strong>
                <div className="result-meta">
                  <span>source：{valueText(hit.source)}</span>
                  <span>DOI：{valueText(hit.doi)}</span>
                  <span>PMID：{valueText(hit.pmid)}</span>
                  <span>relation：{valueText(hit.evidence_relation)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="interpretation-section">
        <h3>天然产物记录</h3>
        {groups.length === 0 ? (
          <p className="muted-text">当前没有可展示的天然产物候选记录。</p>
        ) : (
          <div className="np-record-groups">
            {groups.map((group) => (
              <div key={group.title} className="np-record-group">
                <h4>{group.title}</h4>
                <ul>
                  {group.rows.slice(0, 4).map((row) => (
                    <li key={`${valueText(row.rank)}-${valueText(row.compound_name)}`}>
                      {valueText(row.compound_name)} · {valueText(row.producer_taxon)} ·
                      {valueText(row.taxonomy_distance)} · tier {valueText(row.evidence_tier)}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="interpretation-section">
        <h3>下一步验证建议</h3>
        <ul>
          {item.next_steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ul>
      </section>

      <section className="interpretation-section">
        <h3>科学解释</h3>
        <div className="answer-lead">
          {item.grounded_answer.answer.split(/\n+/).map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </div>
      </section>

      <details className="advanced-settings">
        <summary>详细证据</summary>
        <ProvenanceBlock data={item.detailed_evidence} defaultOpen={false} />
      </details>
    </article>
  )
}

export function ResultsPage() {
  const [taxon, setTaxon] = useState('Streptomyces')
  const [metabolite, setMetabolite] = useState('M1023')
  const [direction, setDirection] = useState('positive')
  const [effectSize, setEffectSize] = useState('0.72')
  const [pValue, setPValue] = useState('0.003')
  const [method, setMethod] = useState('16S genus-level')
  const [useLlm, setUseLlm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null)
  const [result, setResult] = useState<ResultsInterpretationResponse | null>(null)

  async function interpretFinding() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.interpretResult({
        taxon,
        metabolite,
        association_direction: direction,
        effect_size: Number(effectSize),
        p_value: pValue.trim() ? Number(pValue) : null,
        observation_method: method,
        use_llm: useLlm,
        retrieval_mode: 'hybrid',
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

  async function runDemo() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.runResultsDemo({ use_llm: useLlm, retrieval_mode: 'hybrid' })
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
    await interpretFinding()
  }

  const invalidNumber = !Number.isFinite(Number(effectSize)) || (pValue.trim() !== '' && !Number.isFinite(Number(pValue)))

  return (
    <div className="feature-page results-page">
      <PageHeader
        className="feature-page-header"
        title="结果解释"
        subtitle="将你的微生物–代谢物关联结果转化为有外部证据支持的科学解释"
      />

      <form className="card results-form" onSubmit={handleSubmit}>
        <fieldset className="form-section">
          <legend className="form-section-title">关联对象</legend>
          <p className="form-section-desc">填写待解释的微生物分类单元与代谢物或特征编号。</p>
          <div className="form-grid">
            <div className="form-field form-field--half">
              <label htmlFor="result-taxon">
                分类单元
                <span className="form-label-en">Taxon</span>
              </label>
              <input
                id="result-taxon"
                value={taxon}
                onChange={(e) => setTaxon(e.target.value)}
                placeholder="例如 Streptomyces"
                required
              />
            </div>
            <div className="form-field form-field--half">
              <label htmlFor="result-metabolite">
                代谢物 / 特征
                <span className="form-label-en">Metabolite / Feature</span>
              </label>
              <input
                id="result-metabolite"
                value={metabolite}
                onChange={(e) => setMetabolite(e.target.value)}
                placeholder="例如 M1023"
                required
              />
            </div>
            <div className="form-field form-field--full">
              <label className="checkbox-label" htmlFor="results-use-llm">
                <input
                  id="results-use-llm"
                  type="checkbox"
                  checked={useLlm}
                  onChange={(e) => setUseLlm(e.target.checked)}
                />
                LLM 增强
              </label>
            </div>
          </div>
        </fieldset>

        <fieldset className="form-section">
          <legend className="form-section-title">统计指标</legend>
          <p className="form-section-desc">描述关联方向、效应强度与显著性，用于判断证据支持程度。</p>
          <div className="form-grid">
            <div className="form-field form-field--third">
              <label htmlFor="result-direction">
                关联方向
                <span className="form-label-en">Direction</span>
              </label>
              <select id="result-direction" value={direction} onChange={(e) => setDirection(e.target.value)}>
                <option value="positive">正相关 (positive)</option>
                <option value="negative">负相关 (negative)</option>
                <option value="unknown">未知 (unknown)</option>
              </select>
            </div>
            <div className="form-field form-field--third">
              <label htmlFor="result-effect">
                效应量 / 相关系数
                <span className="form-label-en">Effect size / r</span>
              </label>
              <input
                id="result-effect"
                value={effectSize}
                onChange={(e) => setEffectSize(e.target.value)}
                inputMode="decimal"
                placeholder="0.72"
                required
              />
            </div>
            <div className="form-field form-field--third">
              <label htmlFor="result-p">
                P 值
                <span className="form-label-en">P value</span>
              </label>
              <input
                id="result-p"
                value={pValue}
                onChange={(e) => setPValue(e.target.value)}
                inputMode="decimal"
                placeholder="0.003"
              />
            </div>
          </div>
        </fieldset>

        <fieldset className="form-section form-section--last">
          <legend className="form-section-title">实验信息</legend>
          <p className="form-section-desc">说明观测或分析方法，帮助系统评估证据适用边界。</p>
          <div className="form-grid">
            <div className="form-field form-field--full">
              <label htmlFor="result-method">
                观测方法
                <span className="form-label-en">Observation method</span>
              </label>
              <input
                id="result-method"
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                placeholder="例如 16S genus-level"
                required
              />
            </div>
          </div>
        </fieldset>

        <div className="form-actions">
          <button
            type="submit"
            className="btn"
            disabled={loading || invalidNumber || !taxon.trim() || !metabolite.trim()}
          >
            {loading ? '解释中…' : '解释这条发现'}
          </button>
          <button type="button" className="btn btn-secondary" onClick={runDemo} disabled={loading}>
            使用示例数据
          </button>
        </div>
      </form>

      {loading && <p className="loading">正在运行分类学分级、天然产物关联、文献桥接和证据写作…</p>}
      {error && <ErrorPanel message={error.message} detail={error.detail} onRetry={interpretFinding} />}

      {result && (
        <div className="results-output">
          <p className="results-output-summary">
            已解释 <strong>{result.finding_count}</strong> 条发现。
          </p>
          {result.interpretations.map((item) => (
            <ResultInterpretationCard key={item.association_id} item={item} />
          ))}
          {isDebugMode() && (
            <section className="card">
              <h3>运行溯源</h3>
              <ProvenanceBlock data={result.provenance} defaultOpen={false} />
            </section>
          )}
        </div>
      )}
    </div>
  )
}
