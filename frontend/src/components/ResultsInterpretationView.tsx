import type { ResultInterpretation, ResultsInterpretationResponse } from '../api/types'
import { AnswerText } from './AnswerText'
import { Badge } from './Badge'
import { ProvenanceBlock } from './ProvenanceBlock'
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

export function ResultInterpretationCard({ item }: { item: ResultInterpretation }) {
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
        <AnswerText text={item.grounded_answer.answer} className="answer-lead" />
      </section>

      <details className="advanced-settings">
        <summary>详细证据</summary>
        <ProvenanceBlock data={item.detailed_evidence} defaultOpen={false} />
      </details>
    </article>
  )
}

interface ResultsInterpretationViewProps {
  result: ResultsInterpretationResponse
}

export function ResultsInterpretationView({ result }: ResultsInterpretationViewProps) {
  return (
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
  )
}
