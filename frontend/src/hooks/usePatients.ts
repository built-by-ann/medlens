import { useCallback, useEffect, useState } from 'react'
import { archivePatient as archivePatientRequest, listPatients } from '@/api/patients'
import type { ApiError } from '@/api/client'
import type { Patient } from '@/types/api'

interface UsePatientsResult {
  patients: Patient[]
  isLoading: boolean
  error: string | null
  retry: () => void
  archivePatient: (id: number) => Promise<void>
}

/**
 * Fetches the current provider's active patients. Archiving updates local
 * state directly on success (no refetch needed), mirroring usePatientMedications.
 * archivePatient intentionally does not catch its own errors - the caller
 * (the archive confirmation dialog's owning page) owns its own
 * submitting/error UI, the same division of responsibility useAuthForm's
 * onSubmit uses.
 */
export function usePatients(): UsePatientsResult {
  const [patients, setPatients] = useState<Patient[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let ignore = false

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsLoading(true)
    setError(null)

    listPatients()
      .then((result) => {
        if (ignore) return
        setPatients(result)
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
  }, [retryCount])

  const retry = useCallback(() => {
    setRetryCount((count) => count + 1)
  }, [])

  const archivePatient = useCallback(async (id: number) => {
    await archivePatientRequest(id)
    setPatients((current) => current.filter((patient) => patient.id !== id))
  }, [])

  return { patients, isLoading, error, retry, archivePatient }
}
