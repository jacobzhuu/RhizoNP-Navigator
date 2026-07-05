interface ProvenanceBlockProps {
  data: Record<string, unknown>
}

export function ProvenanceBlock({ data }: ProvenanceBlockProps) {
  if (!data || Object.keys(data).length === 0) return null
  return (
    <div>
      <div className="provenance-label">Provenance</div>
      <pre className="provenance">{JSON.stringify(data, null, 2)}</pre>
    </div>
  )
}

export function isFixtureRecord(provenance: Record<string, unknown>): boolean {
  return Boolean(provenance.fixture || provenance.source_database === 'synthetic_fixture')
}
