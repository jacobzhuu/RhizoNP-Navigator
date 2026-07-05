interface ProvenanceBlockProps {
  data: Record<string, unknown>
  defaultOpen?: boolean
}

export function ProvenanceBlock({ data, defaultOpen = true }: ProvenanceBlockProps) {
  if (!data || Object.keys(data).length === 0) return null
  return (
    <details open={defaultOpen} className="provenance-details">
      <summary className="provenance-label">溯源信息</summary>
      <pre className="provenance">{JSON.stringify(data, null, 2)}</pre>
    </details>
  )
}

export function isFixtureRecord(provenance: Record<string, unknown>): boolean {
  return Boolean(provenance.fixture || provenance.source_database === 'synthetic_fixture')
}
