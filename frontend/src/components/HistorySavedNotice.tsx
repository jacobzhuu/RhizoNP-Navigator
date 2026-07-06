import { Link } from 'react-router-dom'

interface HistorySavedNoticeProps {
  historyId: string
}

export function HistorySavedNotice({ historyId }: HistorySavedNoticeProps) {
  return (
    <p className="history-saved-notice">
      已保存到历史记录 ·{' '}
      <Link to={`/history/${historyId}`}>查看详情</Link>
    </p>
  )
}
