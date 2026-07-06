import type { AskRetrievalHit } from '../api/types'
import { Badge } from './Badge'
import { isDebugMode } from '../utils/debug'
import { ProvenanceBlock } from './ProvenanceBlock'

interface EvidenceCardProps {
  hit: AskRetrievalHit
  index: number
}

function externalLink(url: string, label: string) {
  return (
    <a href={url} target="_blank" rel="noopener noreferrer">
      {label}
    </a>
  )
}

function taxonomyBoundary(hit: AskRetrievalHit) {
  const payload = hit.taxonomy_grading
  if (!payload || payload.status !== 'graded') return null
  const grading = payload.grading as Record<string, unknown> | undefined
  if (!grading) return null
  return {
    literatureTaxon: String(payload.literature_taxon ?? ''),
    distance: String(grading.taxonomy_distance ?? ''),
    tier: String(grading.evidence_tier ?? ''),
    maxSupportedClaim: String(grading.max_supported_claim ?? ''),
  }
}

export function EvidenceCard({ hit, index }: EvidenceCardProps) {
  const doiUrl = hit.doi ? (hit.doi.startsWith('http') ? hit.doi : `https://doi.org/${hit.doi}`) : null
  const pmidUrl = hit.pmid ? `https://pubmed.ncbi.nlm.nih.gov/${hit.pmid}/` : null
  const boundary = taxonomyBoundary(hit)

  return (
    <article className="evidence-hit evidence-card">
      <div className="evidence-card-header">
        <strong>#{index + 1} {hit.title}</strong>
        <Badge label={`score ${hit.retrieval_score.toFixed(3)}`} variant="mode" />
      </div>
      <div className="result-meta">
        {hit.journal && <span>期刊：{hit.journal}</span>}
        {hit.year != null && <span>年份：{hit.year}</span>}
        <span>章节：{hit.section}</span>
        {doiUrl ? <span>DOI：{externalLink(doiUrl, hit.doi ?? doiUrl)}</span> : <span>DOI：—</span>}
        {pmidUrl ? <span>PMID：{externalLink(pmidUrl, hit.pmid ?? '')}</span> : <span>PMID：—</span>}
        {hit.source_url && !hit.doi && <span>{externalLink(hit.source_url, '来源链接')}</span>}
      </div>
      <p className="result-text">{hit.supporting_text}</p>
      {hit.matched_terms.length > 0 && (
        <div className="matched-terms">
          {hit.matched_terms.map((term) => (
            <span key={term} className="matched-term">{term}</span>
          ))}
        </div>
      )}
      {boundary && (
        <div className="taxonomy-boundary">
          <strong>证据边界</strong>
          <span>文献分类单元：{boundary.literatureTaxon || '—'}</span>
          <span>距离：{boundary.distance || '—'}</span>
          <span>等级：{boundary.tier || '—'}</span>
          {boundary.maxSupportedClaim && <span>最高主张：{boundary.maxSupportedClaim}</span>}
        </div>
      )}
      {isDebugMode() && <ProvenanceBlock data={hit.provenance} defaultOpen={false} />}
    </article>
  )
}
