import { useCallback, useEffect, useState } from 'react'
import {
  createMedication,
  deleteMedication,
  listMedications,
  updateMedication,
  type MedicationPayload,
} from '@/api/medications'
import type { ApiError } from '@/api/client'
import type { Medication } from '@/types/api'

interface UseMedicationsResult {
  medications: Medication[]
  isLoading: boolean
  error: string | null
  retry: () => void
  addMedication: (payload: MedicationPayload) => Promise<Medication>
  editMedication: (id: number, payload: MedicationPayload) => Promise<Medication>
  removeMedication: (id: number) => Promise<void>
}

/**
 * Fetches the current user's medication list and exposes create/update/delete
 * actions that update local state directly on success (no refetch needed).
 * Mutation functions intentionally do not catch errors themselves - callers
 * (the add form, or a card's own edit/delete state) own their own
 * submitting/error UI, mirroring how useAuthForm's onSubmit is used.
 */
export function useMedications(): UseMedicationsResult {
  const [medications, setMedications] = useState<Medication[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let ignore = false

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsLoading(true)
    setError(null)

    listMedications()
      .then((result) => {
        if (ignore) return
        setMedications(result)
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

  const addMedication = useCallback(async (payload: MedicationPayload) => {
    const created = await createMedication(payload)
    setMedications((current) => [created, ...current])
    return created
  }, [])

  const editMedication = useCallback(async (id: number, payload: MedicationPayload) => {
    const updated = await updateMedication(id, payload)
    setMedications((current) =>
      current.map((medication) => (medication.id === id ? updated : medication)),
    )
    return updated
  }, [])

  const removeMedication = useCallback(async (id: number) => {
    await deleteMedication(id)
    setMedications((current) => current.filter((medication) => medication.id !== id))
  }, [])

  return { medications, isLoading, error, retry, addMedication, editMedication, removeMedication }
}
