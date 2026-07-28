import { useCallback, useEffect, useState } from 'react'
import { listRecentAnalyses } from '@/api/analyses'
import type { ApiError } from '@/api/client'
import type { AnalysisSummary } from '@/types/api'

interface UseRecentAnalysesResult {
  analyses: AnalysisSummary[]
  isLoading: boolean
  error: string | null
  retry: () => void
}

/**
 * Fetches the current user's recent analyses. Kept separate from
 * DashboardPage so the page itself only has to compose UI states, not
 * manage fetch/cancellation logic directly.
 */
export function useRecentAnalyses(limit = 10): UseRecentAnalysesResult {
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let ignore = false

    // This is the standard fetch-on-mount/fetch-on-dependency-change shape
    // (matching React's own docs example for data fetching in an effect):
    // isLoading must flip back to true synchronously, before the request is
    // even sent, so the loading state can't instead be derived during
    // render. react-hooks/set-state-in-effect flags this unconditionally;
    // there is no way to restructure around it here without a data-fetching
    // library, which this codebase deliberately avoids adding.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsLoading(true)
    setError(null)

    listRecentAnalyses(limit)
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

    // Cancels applying a stale response if the component unmounts or this
    // effect re-runs (limit changes, or retry()) before the request settles.
    return () => {
      ignore = true
    }
  }, [limit, retryCount])

  const retry = useCallback(() => {
    setRetryCount((count) => count + 1)
  }, [])

  return { analyses, isLoading, error, retry }
}
