import { useEffect, useState } from 'react'
import { getAnalysisDetail } from '@/api/analyses'
import type { ApiError } from '@/api/client'
import type { AnalysisDetail } from '@/types/api'

interface UseAnalysisPollingResult {
  analysis: AnalysisDetail | null
  error: string | null
  // Re-runs the poll from scratch. A failure here means the status check
  // itself couldn't be confirmed (e.g. a transient network error) - the
  // analysis this is polling for may already exist and be fine, so this
  // only restarts polling rather than creating anything new (contrast
  // AnalysisProcessingPage's own retry, which calls submit() again).
  retry: () => void
}

/**
 * Polls GET /patients/{patientId}/analyses/{analysisId} until the analysis
 * reaches a terminal status (completed or failed), then stops.
 *
 * Analysis creation today runs synchronously inside the create request, so
 * in practice the very first fetch here usually already observes a terminal
 * status. This still polls pending/processing on a real interval rather
 * than assuming that, so the Analysis Processing page keeps working
 * correctly if analysis creation ever becomes asynchronous on the backend.
 *
 * Pass null for analysisId to keep this idle (e.g. before an analysis has
 * been created yet).
 */
export function useAnalysisPolling(
  patientId: number,
  analysisId: number | null,
  intervalMs = 2000,
): UseAnalysisPollingResult {
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    if (analysisId === null) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setAnalysis(null)
      setError(null)
      return
    }

    let ignore = false
    let timeoutId: ReturnType<typeof setTimeout>

    async function poll() {
      try {
        const result = await getAnalysisDetail(patientId, analysisId as number)
        if (ignore) return
        setError(null)
        setAnalysis(result)

        if (result.status === 'pending' || result.status === 'processing') {
          timeoutId = setTimeout(poll, intervalMs)
        }
      } catch (caughtError) {
        if (ignore) return
        setError((caughtError as ApiError).message)
      }
    }

    void poll()

    return () => {
      ignore = true
      clearTimeout(timeoutId)
    }
  }, [patientId, analysisId, intervalMs, retryCount])

  function retry() {
    setRetryCount((current) => current + 1)
  }

  return { analysis, error, retry }
}
