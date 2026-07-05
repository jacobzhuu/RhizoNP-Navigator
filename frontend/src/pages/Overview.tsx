const FLOW_STEPS = [
  'Scientific Query / Omics Data',
  'Literature Retrieval',
  'Taxonomy-aware Evidence Grading',
  'Natural Product Candidate Linking',
  'Grounded Scientific Report',
]

const CAPABILITIES = [
  {
    title: 'Literature Retrieval',
    description: 'BM25, dense, hybrid, and reranked search over indexed paper chunks with provenance traces.',
    scope: 'Synthetic fixture corpus in MVP; not PubMed-wide retrieval.',
    link: '/literature',
  },
  {
    title: 'Taxonomy-aware Grading',
    description: 'Grades evidence strength based on taxonomic distance between query and literature taxa.',
    scope: 'Rule-based policy; genus-level 16S cannot support strain claims.',
    link: '/evidence-grader',
  },
  {
    title: 'Natural Product Linking',
    description: 'Ranks candidate compounds by taxonomy distance, compound match, and evidence tier.',
    scope: 'Synthetic NP fixture records; not a comprehensive NP database.',
    link: '/natural-products',
  },
  {
    title: 'Own-data Pipeline',
    description: 'Runs omics association CSV through grading and candidate linking.',
    scope: 'Local CSV fixtures; no browser upload in MVP.',
    link: '/own-data',
  },
  {
    title: 'Grounded Report Writer',
    description: 'Generates evidence-bound answers with claims, refs, and validation suggestions.',
    scope: 'Deterministic fallback writer; remote LLM disabled in MVP.',
    link: '/grounded-report',
  },
  {
    title: 'Entity & Dataset API',
    description: 'Read-only access to normalized taxa, compounds, evidence, and omics associations.',
    scope: 'Requires PostgreSQL with loaded fixtures.',
    link: 'http://127.0.0.1:8000/docs',
    external: true,
  },
]

export function OverviewPage() {
  return (
    <>
      <header className="page-header">
        <h1>RhizoNP Navigator</h1>
        <p className="subtitle">
          Evidence-Grounded AI for Plant–Microbe and Microbial Natural Product Research
        </p>
      </header>

      <div className="card">
        <h2>Scientific Workflow</h2>
        <div className="flow-diagram">
          {FLOW_STEPS.map((step, i) => (
            <span key={step} style={{ display: 'contents' }}>
              <span className="flow-step">{step}</span>
              {i < FLOW_STEPS.length - 1 && <span className="flow-arrow">→</span>}
            </span>
          ))}
        </div>
        <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', margin: 0 }}>
          Each stage preserves provenance and applies conservative evidence grading. Metrics and
          benchmarks apply only to declared synthetic/MVP replay scope.
        </p>
      </div>

      <div className="capability-grid">
        {CAPABILITIES.map((cap) => (
          <div key={cap.title} className="card capability-card">
            <h3>{cap.title}</h3>
            <p>{cap.description}</p>
            <p style={{ fontSize: '0.8rem', fontStyle: 'italic' }}>
              Scope: {cap.scope}
            </p>
            {cap.external ? (
              <a href={cap.link} target="_blank" rel="noopener noreferrer">
                Open API Docs →
              </a>
            ) : (
              <a href={cap.link}>Explore →</a>
            )}
          </div>
        ))}
      </div>

      <div className="panel-info" style={{ marginTop: '1rem' }}>
        <strong>MVP Boundaries</strong>
        <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1.25rem' }}>
          <li>No unsupported performance claims — evaluation metrics are fixture-scoped only.</li>
          <li>Correlation is not causation; taxonomy grading limits claim strength.</li>
          <li>Remote LLM calls are disabled; writer uses deterministic fallback.</li>
          <li>Literature search requires a running PostgreSQL instance with loaded fixtures.</li>
        </ul>
      </div>
    </>
  )
}
