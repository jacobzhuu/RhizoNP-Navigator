import type { AskResponse } from '../api/types'
import { AnswerText } from './AnswerText'
import { Badge } from './Badge'
import { EvidenceCard } from './EvidenceCard'
import { LimitationsPanel, WarningPanel } from './Panels'
import { ProvenanceBlock } from './ProvenanceBlock'
import { isDebugMode } from '../utils/debug'

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
  if (mode === 'deepseek_applied') return 'LLM 通用知识+证据上下文'
  if (mode === 'deepseek_general_knowledge') return 'LLM 通用知识回答'
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
    item.includes('RAG') ||
    item.includes('通用知识') ||
    item.includes('本地知识库')
  )
  return (preferred.length ? preferred : items).slice(0, 4)
}

interface AskResultViewProps {
  result: AskResponse
  useLlm?: boolean
}

export function AskResultView({ result, useLlm = true }: AskResultViewProps) {
  return (
    <>
      <section className="card">
        <h3>最终回答</h3>
        <div className="badge-row">
          <Badge label={statusLabel(result.answer.status)} variant={statusVariant(result.answer.status)} />
          <Badge label={writerModeLabel(result.answer.writer_mode)} variant="mode" />
        </div>
        <AnswerText text={result.answer.answer} className="answer-lead" />

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
              useLlm
                ? '已启用大模型写作时，最终回答可提供通用知识补充，但会明确标注本地知识库未命中。'
                : '最终回答会进入证据不足状态，不会编造引用或结论。',
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
  )
}
