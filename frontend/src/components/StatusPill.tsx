import { useEffect, useState } from 'react'
import { api } from '../api/client'

type PillState = 'loading' | 'ready' | 'degraded' | 'unavailable' | 'offline'

const LABELS: Record<PillState, string> = {
  loading: '检查中…',
  ready: '服务就绪',
  degraded: '服务降级',
  unavailable: '服务不可用',
  offline: '后端离线',
}

export function StatusPill() {
  const [state, setState] = useState<PillState>('loading')
  const [detail, setDetail] = useState<string | undefined>()

  useEffect(() => {
    let active = true

    async function poll() {
      try {
        const readiness = await api.readiness()
        if (!active) return
        setState(readiness.status as PillState)
        setDetail(readiness.warnings[0])
      } catch {
        try {
          await api.health()
          if (!active) return
          setState('degraded')
          setDetail('Readiness 检查失败')
        } catch {
          if (!active) return
          setState('offline')
          setDetail(undefined)
        }
      }
    }

    poll()
    const timer = window.setInterval(poll, 30000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  return (
    <span
      className={`status-pill status-pill--${state}`}
      title={detail}
      aria-label={LABELS[state]}
    >
      <span className="status-pill-dot" aria-hidden="true" />
      {LABELS[state]}
    </span>
  )
}
