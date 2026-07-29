import { useCallback, useEffect, useState } from 'react'
import { listAnalyses } from '@/api/analyses'
import type { ApiError } from '@/api/client'
import type { AnalysisSummary } from '@/types/api'

interface UsePatientAnalysesResult {
  analyses: AnalysisSummary[]
  isLoading: boolean
  error: string | null
  retry: () => void
}

/**
 * Fetches one patient's analysis history. Re-fetches whenever patientId
 * changes, so navigating from one patient's analyses to another's doesn't
 * show stale data. Scoped to a single patientId - there is no cross-patient
 * or global analysis list anywhere in this hook.
 */
export function usePatientAnalyses(patientId: number, limit = 10): UsePatientAnalysesResult {
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let ignore = false

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsLoading(true)
    setError(null)

    listAnalyses(patientId, limit)
      .then((result) => {
        if (ignore) return
        setAnalyses(result)
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
  }, [patientId, limit, retryCount])

  const retry = useCallback(() => {
    setRetryCount((count) => count + 1)
  }, [])

  return { analyses, isLoading, error, retry }
}
