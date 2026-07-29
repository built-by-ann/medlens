import { useCallback, useEffect, useState } from 'react'
import { getAnalysisDetail } from '@/api/analyses'
import type { ApiError } from '@/api/client'
import type { AnalysisDetail } from '@/types/api'

interface UseAnalysisDetailResult {
  analysis: AnalysisDetail | null
  isLoading: boolean
  error: string | null
  retry: () => void
}

/**
 * Fetches a single analysis's metadata for AnalysisDetailPage. A not-found
 * or not-owned analysis (or patient) surfaces through the normal `error`
 * state, matching usePatient - the backend's own "Analysis not found" /
 * "Patient not found" detail already reads correctly as an error message.
 */
export function useAnalysisDetail(patientId: number, analysisId: number): UseAnalysisDetailResult {
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let ignore = false

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsLoading(true)
    setError(null)

    getAnalysisDetail(patientId, analysisId)
      .then((result) => {
        if (ignore) return
        setAnalysis(result)
      })
      .catch((caughtError: unknown) => {
        if (ignore) return
        setError((caughtError as ApiError).message)
      })
      .finally(() => {
        if (!ignore) setIsLoading(false)
      })

    return () => {
      ignore = true
    }
  }, [patientId, analysisId, retryCount])

  const retry = useCallback(() => {
    setRetryCount((count) => count + 1)
  }, [])

  return { analysis, isLoading, error, retry }
}
