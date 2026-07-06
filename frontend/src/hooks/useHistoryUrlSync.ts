import { useCallback, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'

interface UseHistoryUrlSyncOptions {
  historyId: string | null | undefined
  restoring: boolean
  onRestore: (historyId: string) => void | Promise<void>
}

export function useHistoryUrlSync({
  historyId,
  restoring,
  onRestore,
}: UseHistoryUrlSyncOptions) {
  const [searchParams, setSearchParams] = useSearchParams()
  const urlHistoryId = searchParams.get('history')
  const restoreTargetRef = useRef<string | null>(null)

  useEffect(() => {
    if (!urlHistoryId) {
      restoreTargetRef.current = null
      return
    }
    if (restoring) return
    if (historyId === urlHistoryId) {
      restoreTargetRef.current = urlHistoryId
      return
    }
    if (restoreTargetRef.current === urlHistoryId) return
    restoreTargetRef.current = urlHistoryId
    void onRestore(urlHistoryId)
  }, [urlHistoryId, historyId, restoring, onRestore])

  useEffect(() => {
    if (!historyId || restoring) return
    if (searchParams.get('history') === historyId) return
    setSearchParams({ history: historyId }, { replace: true })
  }, [historyId, restoring, searchParams, setSearchParams])

  const clearHistoryParam = useCallback(() => {
    if (!searchParams.has('history')) return
    restoreTargetRef.current = null
    setSearchParams({}, { replace: true })
  }, [searchParams, setSearchParams])

  return { clearHistoryParam, urlHistoryId }
}
