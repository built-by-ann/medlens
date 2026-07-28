import { useCallback, useEffect, useState } from 'react'
import { getPatient } from '@/api/patients'
import type { ApiError } from '@/api/client'
import type { Patient } from '@/types/api'

interface UsePatientResult {
  patient: Patient | null
  isLoading: boolean
  error: string | null
  retry: () => void
}

/**
 * Fetches a single patient by id, for the Overview and Edit pages. A
 * not-found or not-owned patient surfaces through `error` exactly like any
 * other failed request - the backend's 404 detail ("Patient not found")
 * already reads correctly as an error message, so there is no separate
 * not-found UI state to build.
 */
export function usePatient(patientId: number): UsePatientResult {
  const [patient, setPatient] = useState<Patient | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let ignore = false

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsLoading(true)
    setError(null)

    getPatient(patientId)
      .then((result) => {
        if (ignore) return
        setPatient(result)
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
  }, [patientId, retryCount])

  const retry = useCallback(() => {
    setRetryCount((count) => count + 1)
  }, [])

  return { patient, isLoading, error, retry }
}
