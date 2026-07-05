import type { ReactNode } from 'react'

interface WarningPanelProps {
  title?: string
  items: string[]
}

export function WarningPanel({ title = 'Warnings', items }: WarningPanelProps) {
  if (items.length === 0) return null
  return (
    <div className="panel-warning">
      <strong>{title}</strong>
      <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.25rem' }}>
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

export function LimitationsPanel({ items }: { items: string[] }) {
  if (items.length === 0) return null
  return (
    <div className="panel-info">
      <strong>Limitations</strong>
      <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.25rem' }}>
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

export function ErrorPanel({ message, detail }: { message: string; detail?: string }) {
  return (
    <div className="panel-error">
      <strong>{message}</strong>
      {detail && <p style={{ margin: '0.35rem 0 0' }}>{detail}</p>}
    </div>
  )
}

export function InfoPanel({ children }: { children: ReactNode }) {
  return <div className="panel-info">{children}</div>
}
