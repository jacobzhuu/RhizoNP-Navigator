import { Link, useLocation } from 'react-router-dom'
import { useAskSession } from '../context/AskSessionContext'
import { useResultsSession } from '../context/ResultsSessionContext'
import { IconMessage, IconFlask } from './icons'

export function BackgroundTaskBanner() {
  const { pathname } = useLocation()
  const ask = useAskSession()
  const results = useResultsSession()

  const askRunning = ask.loading && pathname !== '/ask'
  const resultsRunning = results.loading && pathname !== '/results'

  if (!askRunning && !resultsRunning) return null

  return (
    <div className="background-task-banner" role="status" aria-live="polite">
      {askRunning && (
        <Link to="/ask" className="background-task-banner-item">
          <IconMessage size={16} />
          <span>科研问答分析中…</span>
          <span className="background-task-banner-action">返回查看</span>
        </Link>
      )}
      {resultsRunning && (
        <Link to="/results" className="background-task-banner-item">
          <IconFlask size={16} />
          <span>结果解释生成中…</span>
          <span className="background-task-banner-action">返回查看</span>
        </Link>
      )}
    </div>
  )
}
