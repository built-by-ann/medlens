import { useCallback, useEffect, useState } from 'react'
import { deleteClinicalDocument, listClinicalDocuments } from '@/api/clinicalDocuments'
import type { ApiError } from '@/api/client'
import type { ClinicalDocument } from '@/types/api'

interface UsePatientClinicalDocumentsResult {
  documents: ClinicalDocument[]
  isLoading: boolean
  error: string | null
  retry: () => void
  removeDocument: (id: number) => Promise<void>
}

/**
 * Fetches one patient's clinical documents and exposes a delete action that
 * updates local state directly on success (no refetch needed). Re-fetches
 * whenever patientId changes, so navigating from one patient's documents to
 * another's doesn't show stale data.
 *
 * Scoped to a single patientId; there is no cross-patient document state
 * anywhere in this hook. There is no add/create action here: documents are
 * created through the Upload workflow (useCreateAnalysis), which already
 * owns that flow; this hook only lists and removes what already exists.
 */
export function usePatientClinicalDocuments(patientId: number): UsePatientClinicalDocumentsResult {
  const [documents, setDocuments] = useState<ClinicalDocument[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let ignore = false

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsLoading(true)
    setError(null)

    listClinicalDocuments(patientId)
      .then((result) => {
        if (ignore) return
        setDocuments(result)
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

  const removeDocument = useCallback(
    async (id: number) => {
      await deleteClinicalDocument(patientId, id)
      setDocuments((current) => current.filter((document) => document.id !== id))
    },
    [patientId],
  )

  return { documents, isLoading, error, retry, removeDocument }
}
