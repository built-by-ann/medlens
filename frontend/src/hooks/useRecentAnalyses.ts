import { useCallback, useEffect, useState } from 'react'
import { getRecentAnalyses } from '@/api/analyses'
import type { ApiError } from '@/api/client'
import type { RecentAnalysis } from '@/types/api'

interface UseRecentAnalysesResult {
  analyses: RecentAnalysis[]
  isLoading: boolean
  error: string | null
  retry: () => void
}

/**
 * The Dashboard's Recent Analyses feed (Issue #157): cross-patient, unlike
 * usePatientAnalyses, and read-only: no delete action here, since deleting
 * an analysis remains a patient-page action (AnalysisDetailPage).
 */
export function useRecentAnalyses(limit = 3): UseRecentAnalysesResult {
  const [analyses, setAnalyses] = useState<RecentAnalysis[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let ignore = false

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsLoading(true)
    setError(null)

    getRecentAnalyses(limit)
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
  }, [limit, retryCount])

  const retry = useCallback(() => {
    setRetryCount((count) => count + 1)
  }, [])

  return { analyses, isLoading, error, retry }
}
