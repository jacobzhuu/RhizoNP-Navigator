import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { api } from '../api/client'
import {
  ApiError,
  BackendUnavailableError,
  type AskRequest,
  type AskResponse,
} from '../api/types'

interface AskError {
  message: string
  detail?: string
}

interface AskSessionState {
  question: string
  retrievalMode: string
  topK: number
  maxQueries: number
  useLlm: boolean
  showAdvanced: boolean
  loading: boolean
  loadingStep: number
  restoring: boolean
  error: AskError | null
  result: AskResponse | null
  historyId: string | null
}

interface AskSessionContextValue extends AskSessionState {
  setQuestion: (value: string) => void
  setRetrievalMode: (value: string) => void
  setTopK: (value: number) => void
  setMaxQueries: (value: number) => void
  setUseLlm: (value: boolean) => void
  setShowAdvanced: (value: boolean) => void
  submitQuestion: () => Promise<void>
  restoreFromHistory: (historyId: string) => Promise<void>
  clearResult: () => void
}

const AskSessionContext = createContext<AskSessionContextValue | null>(null)

function parseAskRequest(payload: Record<string, unknown>): Partial<AskRequest> {
  return {
    question: typeof payload.question === 'string' ? payload.question : '',
    retrieval_mode: typeof payload.retrieval_mode === 'string' ? payload.retrieval_mode : 'hybrid_rerank',
    top_k: typeof payload.top_k === 'number' ? payload.top_k : 5,
    max_queries: typeof payload.max_queries === 'number' ? payload.max_queries : 3,
    use_llm: typeof payload.use_llm === 'boolean' ? payload.use_llm : true,
  }
}

export function AskSessionProvider({ children }: { children: ReactNode }) {
  const [question, setQuestion] = useState('')
  const [retrievalMode, setRetrievalMode] = useState('hybrid_rerank')
  const [topK, setTopK] = useState(5)
  const [maxQueries, setMaxQueries] = useState(3)
  const [useLlm, setUseLlm] = useState(true)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadingStep, setLoadingStep] = useState(0)
  const [restoring, setRestoring] = useState(false)
  const [error, setError] = useState<AskError | null>(null)
  const [result, setResult] = useState<AskResponse | null>(null)
  const stepTimerRef = useRef<number | null>(null)

  const historyId = result?.history_id ?? null

  useEffect(() => {
    if (!loading) {
      if (stepTimerRef.current != null) {
        window.clearInterval(stepTimerRef.current)
        stepTimerRef.current = null
      }
      return
    }
    setLoadingStep(0)
    stepTimerRef.current = window.setInterval(() => {
      setLoadingStep((prev) => (prev < 3 ? prev + 1 : prev))
    }, 1200)
    return () => {
      if (stepTimerRef.current != null) {
        window.clearInterval(stepTimerRef.current)
        stepTimerRef.current = null
      }
    }
  }, [loading])

  const restoreFromHistory = useCallback(async (id: string) => {
    setRestoring(true)
    setError(null)
    try {
      const detail = await api.getHistory(id)
      if (detail.kind !== 'ask') {
        setError({ message: '历史记录类型不匹配', detail: '该记录不是科研问答结果。' })
        return
      }
      const request = parseAskRequest(detail.request)
      const response = detail.response as unknown as AskResponse
      setQuestion(request.question ?? '')
      if (request.retrieval_mode) setRetrievalMode(request.retrieval_mode)
      if (request.top_k != null) setTopK(request.top_k)
      if (request.max_queries != null) setMaxQueries(request.max_queries)
      if (request.use_llm != null) setUseLlm(request.use_llm)
      setResult({ ...response, history_id: detail.history_id })
    } catch (err) {
      if (err instanceof BackendUnavailableError || err instanceof ApiError) {
        setError({ message: err.message, detail: err instanceof ApiError ? err.detail : undefined })
      } else {
        setError({ message: '无法加载历史记录', detail: String(err) })
      }
    } finally {
      setRestoring(false)
    }
  }, [])

  const submitQuestion = useCallback(async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.ask({
        question,
        retrieval_mode: retrievalMode,
        top_k: topK,
        max_queries: maxQueries,
        use_llm: useLlm,
      })
      setLoadingStep(3)
      setResult(data)
    } catch (err) {
      if (err instanceof BackendUnavailableError || err instanceof ApiError) {
        setError({ message: err.message, detail: err instanceof ApiError ? err.detail : undefined })
      } else {
        setError({ message: '意外错误', detail: String(err) })
      }
    } finally {
      setLoading(false)
    }
  }, [question, retrievalMode, topK, maxQueries, useLlm])

  const clearResult = useCallback(() => {
    setResult(null)
    setError(null)
  }, [])

  const value = useMemo<AskSessionContextValue>(
    () => ({
      question,
      retrievalMode,
      topK,
      maxQueries,
      useLlm,
      showAdvanced,
      loading,
      loadingStep,
      restoring,
      error,
      result,
      historyId,
      setQuestion,
      setRetrievalMode,
      setTopK,
      setMaxQueries,
      setUseLlm,
      setShowAdvanced,
      submitQuestion,
      restoreFromHistory,
      clearResult,
    }),
    [
      question,
      retrievalMode,
      topK,
      maxQueries,
      useLlm,
      showAdvanced,
      loading,
      loadingStep,
      restoring,
      error,
      result,
      historyId,
      submitQuestion,
      restoreFromHistory,
      clearResult,
    ],
  )

  return <AskSessionContext.Provider value={value}>{children}</AskSessionContext.Provider>
}

export function useAskSession(): AskSessionContextValue {
  const context = useContext(AskSessionContext)
  if (!context) {
    throw new Error('useAskSession must be used within AskSessionProvider')
  }
  return context
}
