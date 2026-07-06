import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import {
  ApiError,
  BackendUnavailableError,
  type AskResponse,
  type HistoryKind,
  type HistoryListItem,
  type ResultsInterpretationResponse,
} from '../api/types'
import { AskResultView } from '../components/AskResultView'
import { Badge } from '../components/Badge'
import { IconChevronRight, IconClock, IconFlask, IconMessage } from '../components/icons'
import { ErrorPanel } from '../components/Panels'
import { EmptyState, FeaturePage, PageHeader } from '../components/PageShell'
import { ResultsInterpretationView } from '../components/ResultsInterpretationView'

type FilterKind = HistoryKind | 'all'

const FILTER_OPTIONS: { value: FilterKind; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'ask', label: '科研问答' },
  { value: 'results', label: '结果解释' },
]

function kindLabel(kind: HistoryKind): string {
  return kind === 'ask' ? '科研问答' : '结果解释'
}

function statusLabel(status: string): string {
  if (status === 'SUPPORTED') return '证据支持'
  if (status === 'PARTIALLY_SUPPORTED') return '部分支持'
  if (status === 'INSUFFICIENT_EVIDENCE') return '证据不足'
  if (status === 'CONFLICTING_EVIDENCE') return '证据冲突'
  if (status === 'UNSUPPORTED') return '不支持'
  return status
}

function statusVariant(status: string): 'supported' | 'partial' | 'insufficient' | 'unsupported' | 'mode' {
  if (status === 'SUPPORTED') return 'supported'
  if (status === 'PARTIALLY_SUPPORTED') return 'partial'
  if (status === 'INSUFFICIENT_EVIDENCE' || status === 'CONFLICTING_EVIDENCE') return 'insufficient'
  if (status === 'UNSUPPORTED') return 'unsupported'
  return 'mode'
}

function formatDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function HistoryListItemCard({ item }: { item: HistoryListItem }) {
  const ItemIcon = item.kind === 'ask' ? IconMessage : IconFlask
  const iconClass = item.kind === 'ask' ? 'history-list-item-icon--ask' : 'history-list-item-icon--results'

  return (
    <Link to={`/history/${item.history_id}`} className="history-list-item card">
      <span className={`history-list-item-icon ${iconClass}`}>
        <ItemIcon size={20} />
      </span>
      <div className="history-list-item-body">
        <div className="history-list-item-header">
          <Badge label={kindLabel(item.kind)} variant="kind" />
          <Badge label={statusLabel(item.status)} variant={statusVariant(item.status)} />
          <time className="history-list-item-time" dateTime={item.created_at}>
            <IconClock size={12} />
            {formatDate(item.created_at)}
          </time>
        </div>
        <h3 className="history-list-item-title">{item.title}</h3>
        {item.summary && <p className="history-list-item-summary">{item.summary}</p>}
      </div>
      <IconChevronRight size={20} className="history-list-item-chevron" />
    </Link>
  )
}

function HistoryDetail({ historyId }: { historyId: string }) {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null)
  const [askResult, setAskResult] = useState<AskResponse | null>(null)
  const [resultsResult, setResultsResult] = useState<ResultsInterpretationResponse | null>(null)
  const [meta, setMeta] = useState<{ kind: HistoryKind; created_at: string } | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    setAskResult(null)
    setResultsResult(null)
    api.getHistory(historyId)
      .then((detail) => {
        if (!active) return
        setMeta({ kind: detail.kind, created_at: detail.created_at })
        if (detail.kind === 'ask') {
          setAskResult(detail.response as unknown as AskResponse)
        } else {
          setResultsResult(detail.response as unknown as ResultsInterpretationResponse)
        }
      })
      .catch((err) => {
        if (!active) return
        if (err instanceof BackendUnavailableError || err instanceof ApiError) {
          setError({ message: err.message, detail: err instanceof ApiError ? err.detail : undefined })
        } else {
          setError({ message: '无法加载历史记录', detail: String(err) })
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [historyId])

  return (
    <div className="history-detail">
      <button type="button" className="btn btn-secondary history-back-btn" onClick={() => navigate('/history')}>
        返回列表
      </button>

      {loading && <p className="loading">加载历史记录…</p>}
      {error && <ErrorPanel message={error.message} detail={error.detail} />}

      {meta && !loading && !error && (
        <div className="history-detail-meta card">
          <Badge label={kindLabel(meta.kind)} variant="kind" />
          <time dateTime={meta.created_at}>{formatDate(meta.created_at)}</time>
        </div>
      )}

      {askResult && <AskResultView result={askResult} />}
      {resultsResult && <ResultsInterpretationView result={resultsResult} />}
    </div>
  )
}

export function HistoryPage() {
  const { historyId } = useParams()
  const [filter, setFilter] = useState<FilterKind>('all')
  const [items, setItems] = useState<HistoryListItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null)

  useEffect(() => {
    if (historyId) return
    let active = true
    setLoading(true)
    setError(null)
    api.listHistory({ kind: filter === 'all' ? undefined : filter, limit: 50 })
      .then((data) => {
        if (!active) return
        setItems(data.items)
        setTotal(data.total)
      })
      .catch((err) => {
        if (!active) return
        if (err instanceof BackendUnavailableError || err instanceof ApiError) {
          setError({ message: err.message, detail: err instanceof ApiError ? err.detail : undefined })
        } else {
          setError({ message: '无法加载历史记录', detail: String(err) })
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [filter, historyId])

  if (historyId) {
    return (
      <FeaturePage>
        <PageHeader
          icon={IconClock}
          iconTheme="slate"
          title="历史记录详情"
          subtitle="查看已保存的问答或结果解释"
        />
        <HistoryDetail historyId={historyId} />
      </FeaturePage>
    )
  }

  return (
    <FeaturePage>
      <PageHeader
        icon={IconClock}
        iconTheme="slate"
        title="历史记录"
        subtitle="浏览已保存的科研问答与结果解释"
      />

      <div className="pill-filter-group" role="tablist" aria-label="历史记录筛选">
        {FILTER_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={filter === option.value}
            className={`pill-filter${filter === option.value ? ' active' : ''}`}
            onClick={() => setFilter(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>

      {loading && <p className="loading">加载历史记录…</p>}
      {error && <ErrorPanel message={error.message} detail={error.detail} />}

      {!loading && !error && items.length === 0 && (
        <EmptyState
          title="暂无历史记录"
          description="在科研问答或结果解释页面提交后，记录会自动保存在此处。"
        />
      )}

      {!loading && !error && items.length > 0 && (
        <>
          <p className="history-list-count muted-text">共 {total} 条记录</p>
          <div className="history-list">
            {items.map((item) => (
              <HistoryListItemCard key={item.history_id} item={item} />
            ))}
          </div>
        </>
      )}
    </FeaturePage>
  )
}
