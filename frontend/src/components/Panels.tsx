import type { ReactNode } from 'react'

interface WarningPanelProps {
  title?: string
  items: string[]
}

export function WarningPanel({ title = '警告', items }: WarningPanelProps) {
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
      <strong>局限性</strong>
      <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.25rem' }}>
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

interface ErrorPanelProps {
  message: string
  detail?: string
  onRetry?: () => void
}

export function ErrorPanel({ message, detail, onRetry }: ErrorPanelProps) {
  return (
    <div className="panel-error" role="alert">
      <strong>{message}</strong>
      {detail && <p style={{ margin: '0.35rem 0 0' }}>{detail}</p>}
      {onRetry && (
        <button type="button" className="btn btn-secondary" style={{ marginTop: '0.75rem' }} onClick={onRetry}>
          重试
        </button>
      )}
    </div>
  )
}

export function InfoPanel({ children }: { children: ReactNode }) {
  return <div className="panel-info">{children}</div>
}
