import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api } from '../api/client'
import {
  ApiError,
  BackendUnavailableError,
  type ResultInterpretationRequest,
  type ResultsInterpretationResponse,
} from '../api/types'

interface ResultsError {
  message: string
  detail?: string
}

interface ResultsSessionContextValue {
  taxon: string
  metabolite: string
  direction: string
  effectSize: string
  pValue: string
  method: string
  useLlm: boolean
  exampleIndex: number
  activeExampleIndex: number | null
  loading: boolean
  restoring: boolean
  error: ResultsError | null
  result: ResultsInterpretationResponse | null
  historyId: string | null
  setTaxon: (value: string) => void
  setMetabolite: (value: string) => void
  setDirection: (value: string) => void
  setEffectSize: (value: string) => void
  setPValue: (value: string) => void
  setMethod: (value: string) => void
  setUseLlm: (value: boolean) => void
  setExampleIndex: (value: number | ((prev: number) => number)) => void
  setActiveExampleIndex: (value: number | null) => void
  interpretFinding: () => Promise<void>
  restoreFromHistory: (historyId: string) => Promise<void>
  clearResult: () => void
}

const ResultsSessionContext = createContext<ResultsSessionContextValue | null>(null)

function parseResultsRequest(payload: Record<string, unknown>): {
  taxon: string
  metabolite: string
  direction: string
  effectSize: string
  pValue: string
  method: string
  useLlm: boolean
} {
  return {
    taxon: typeof payload.taxon === 'string' ? payload.taxon : '',
    metabolite: typeof payload.metabolite === 'string' ? payload.metabolite : '',
    direction: typeof payload.association_direction === 'string' ? payload.association_direction : 'positive',
    effectSize: payload.effect_size != null ? String(payload.effect_size) : '',
    pValue: payload.p_value != null ? String(payload.p_value) : '',
    method: typeof payload.observation_method === 'string' ? payload.observation_method : '',
    useLlm: typeof payload.use_llm === 'boolean' ? payload.use_llm : true,
  }
}

export function ResultsSessionProvider({ children }: { children: ReactNode }) {
  const [taxon, setTaxon] = useState('')
  const [metabolite, setMetabolite] = useState('')
  const [direction, setDirection] = useState('positive')
  const [effectSize, setEffectSize] = useState('')
  const [pValue, setPValue] = useState('')
  const [method, setMethod] = useState('')
  const [useLlm, setUseLlm] = useState(true)
  const [exampleIndex, setExampleIndex] = useState(0)
  const [activeExampleIndex, setActiveExampleIndex] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [error, setError] = useState<ResultsError | null>(null)
  const [result, setResult] = useState<ResultsInterpretationResponse | null>(null)

  const historyId = result?.history_id ?? null

  const restoreFromHistory = useCallback(async (id: string) => {
    setRestoring(true)
    setError(null)
    try {
      const detail = await api.getHistory(id)
      if (detail.kind !== 'results') {
        setError({ message: '历史记录类型不匹配', detail: '该记录不是结果解释。' })
        return
      }
      const request = parseResultsRequest(detail.request)
      const response = detail.response as unknown as ResultsInterpretationResponse
      setTaxon(request.taxon)
      setMetabolite(request.metabolite)
      setDirection(request.direction)
      setEffectSize(request.effectSize)
      setPValue(request.pValue)
      setMethod(request.method)
      setUseLlm(request.useLlm)
      setActiveExampleIndex(null)
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

  const interpretFinding = useCallback(async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const body: ResultInterpretationRequest = {
        taxon,
        metabolite,
        association_direction: direction,
        effect_size: Number(effectSize),
        p_value: pValue.trim() ? Number(pValue) : null,
        observation_method: method,
        use_llm: useLlm,
        retrieval_mode: 'hybrid',
      }
      const data = await api.interpretResult(body)
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
  }, [taxon, metabolite, direction, effectSize, pValue, method, useLlm])

  const clearResult = useCallback(() => {
    setResult(null)
    setError(null)
  }, [])

  const value = useMemo<ResultsSessionContextValue>(
    () => ({
      taxon,
      metabolite,
      direction,
      effectSize,
      pValue,
      method,
      useLlm,
      exampleIndex,
      activeExampleIndex,
      loading,
      restoring,
      error,
      result,
      historyId,
      setTaxon,
      setMetabolite,
      setDirection,
      setEffectSize,
      setPValue,
      setMethod,
      setUseLlm,
      setExampleIndex,
      setActiveExampleIndex,
      interpretFinding,
      restoreFromHistory,
      clearResult,
    }),
    [
      taxon,
      metabolite,
      direction,
      effectSize,
      pValue,
      method,
      useLlm,
      exampleIndex,
      activeExampleIndex,
      loading,
      restoring,
      error,
      result,
      historyId,
      interpretFinding,
      restoreFromHistory,
      clearResult,
    ],
  )

  return <ResultsSessionContext.Provider value={value}>{children}</ResultsSessionContext.Provider>
}

export function useResultsSession(): ResultsSessionContextValue {
  const context = useContext(ResultsSessionContext)
  if (!context) {
    throw new Error('useResultsSession must be used within ResultsSessionProvider')
  }
  return context
}
