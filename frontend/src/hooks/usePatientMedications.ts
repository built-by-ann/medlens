import { useCallback, useEffect, useState } from 'react'
import {
  createMedication,
  deleteMedication,
  importMedicationsCsv as importMedicationsCsvRequest,
  listMedications,
  updateMedication,
  type MedicationPayload,
} from '@/api/medications'
import type { ApiError } from '@/api/client'
import type { Medication, MedicationImportSummary } from '@/types/api'

interface UsePatientMedicationsResult {
  medications: Medication[]
  isLoading: boolean
  error: string | null
  retry: () => void
  addMedication: (payload: MedicationPayload) => Promise<Medication>
  editMedication: (id: number, payload: MedicationPayload) => Promise<Medication>
  removeMedication: (id: number) => Promise<void>
  importMedicationsCsv: (file: File) => Promise<MedicationImportSummary>
}

/**
 * Fetches one patient's medication list and exposes create/update/delete
 * actions that update local state directly on success (no refetch
 * needed). Re-fetches whenever patientId changes, so navigating from one
 * patient's medications to another's doesn't show stale data. Mutation
 * functions intentionally do not catch their own errors - callers (the add
 * form, or a card's own edit/delete state) own their own submitting/error
 * UI, mirroring how useAuthForm's onSubmit is used.
 *
 * Scoped to a single patientId rather than any global medication list -
 * there is no cross-patient medication state anywhere in this hook.
 */
export function usePatientMedications(patientId: number): UsePatientMedicationsResult {
  const [medications, setMedications] = useState<Medication[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let ignore = false

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsLoading(true)
    setError(null)

    listMedications(patientId)
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
  }, [patientId, retryCount])

  const retry = useCallback(() => {
    setRetryCount((count) => count + 1)
  }, [])

  const addMedication = useCallback(
    async (payload: MedicationPayload) => {
      const created = await createMedication(patientId, payload)
      setMedications((current) => [created, ...current])
      return created
    },
    [patientId],
  )

  const editMedication = useCallback(
    async (id: number, payload: MedicationPayload) => {
      const updated = await updateMedication(patientId, id, payload)
      setMedications((current) =>
        current.map((medication) => (medication.id === id ? updated : medication)),
      )
      return updated
    },
    [patientId],
  )

  const removeMedication = useCallback(
    async (id: number) => {
      await deleteMedication(patientId, id)
      setMedications((current) => current.filter((medication) => medication.id !== id))
    },
    [patientId],
  )

  // A CSV import can create many medications at once, and the response is
  // only counts (no created medication objects to merge into local state
  // the way addMedication does) - so success re-triggers the same
  // fetch-on-mount effect used for retry(), rather than trying to
  // reconstruct the new rows locally.
  const importMedicationsCsv = useCallback(
    async (file: File) => {
      const summary = await importMedicationsCsvRequest(patientId, file)
      setRetryCount((count) => count + 1)
      return summary
    },
    [patientId],
  )

  return {
    medications,
    isLoading,
    error,
    retry,
    addMedication,
    editMedication,
    removeMedication,
    importMedicationsCsv,
  }
}
