import { useCallback, useRef, useState } from 'react'
import { createClinicalDocumentFromText, uploadClinicalDocumentFile } from '@/api/clinicalDocuments'
import { createAnalysisFromDocuments } from '@/api/analyses'
import type { ApiError } from '@/api/client'

export interface QueuedFile {
  id: number
  file: File
  documentType: string
  // Unset by default; the document is titled from the filename on upload
  // (deriveTitleFromFileName). Only set once a provider edits it, e.g. to
  // resolve a same-name collision with a document already on file.
  title?: string
}

export interface QueuedNote {
  id: number
  title: string
  rawText: string
  documentType: string
}

export interface SubmitInput {
  files: QueuedFile[]
  notes: QueuedNote[]
  // Ids of clinical documents the patient already has on file, selected for
  // reuse rather than uploaded in this submission (Issue #145). These never
  // go through the upload/cache logic below; they're already real
  // ClinicalDocument rows, and are simply included in the same
  // createAnalysisFromDocuments call alongside anything newly uploaded.
  existingDocumentIds?: number[]
}

export interface SaveInput {
  files: QueuedFile[]
  notes: QueuedNote[]
}

interface UseCreateAnalysisResult {
  isSubmitting: boolean
  error: string | null
  failedItemLabel: string | null
  submit: (input: SubmitInput) => Promise<number>
  // Uploads files/notes as real ClinicalDocuments without creating an
  // analysis from them; the "just save" path (Issue #158 follow-up).
  // Returns the resulting document ids.
  saveDocuments: (input: SaveInput) => Promise<number[]>
  invalidateItem: (key: string) => void
}

export function fileItemKey(id: number): string {
  return `file:${id}`
}

export function noteItemKey(id: number): string {
  return `note:${id}`
}

/**
 * Uploads every selected file and pasted note as a ClinicalDocument, then
 * either creates an analysis from all of them (submit, together with any
 * already-existing documents passed via existingDocumentIds; Issue #145,
 * selected from a patient's prior uploads rather than uploaded again here),
 * or stops after uploading (saveDocuments; Issue #158 follow-up, for
 * providers who want documents on file without analyzing them yet).
 *
 * Each item's resulting document id is cached as soon as it succeeds,
 * keyed by its stable queue id (fileItemKey/noteItemKey), not its position.
 * If a later item then fails, the queue up to that point has already been
 * cached, so calling submit()/saveDocuments() again with the same queue
 * reuses those ids instead of re-uploading them, retrying only what didn't
 * already succeed. The cache is owned here, not in UploadPage's state,
 * since it is meaningless outside a single attempt: UploadPage only ever
 * needs to invalidate an entry (when the user edits or removes the
 * associated item, since a cached id would otherwise silently refer to
 * stale content), never read or persist it. It is also cleared
 * automatically once an attempt fully succeeds, since a later attempt
 * reusing the same queue is a new one.
 *
 * Scoped to a single patientId; every uploaded document and the resulting
 * analysis belong to this patient, never a global document/analysis pool.
 */
export function useCreateAnalysis(patientId: number): UseCreateAnalysisResult {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [failedItemLabel, setFailedItemLabel] = useState<string | null>(null)
  const uploadedIds = useRef(new Map<string, number>())

  const invalidateItem = useCallback((key: string) => {
    uploadedIds.current.delete(key)
  }, [])

  const uploadQueuedItems = useCallback(
    async (files: QueuedFile[], notes: QueuedNote[]): Promise<number[]> => {
      const clinicalDocumentIds: number[] = []

      for (const queuedFile of files) {
        const key = fileItemKey(queuedFile.id)
        const cachedId = uploadedIds.current.get(key)

        if (cachedId !== undefined) {
          clinicalDocumentIds.push(cachedId)
          continue
        }

        let documentId: number

        try {
          const document = await uploadClinicalDocumentFile(
            patientId,
            queuedFile.file,
            queuedFile.documentType,
            queuedFile.title,
          )
          documentId = document.id
        } catch (caughtError) {
          setFailedItemLabel(queuedFile.file.name)
          throw caughtError
        }

        uploadedIds.current.set(key, documentId)
        clinicalDocumentIds.push(documentId)
      }

      for (const [index, queuedNote] of notes.entries()) {
        const key = noteItemKey(queuedNote.id)
        const cachedId = uploadedIds.current.get(key)

        if (cachedId !== undefined) {
          clinicalDocumentIds.push(cachedId)
          continue
        }

        const title = queuedNote.title.trim() || `Note ${index + 1}`
        let documentId: number

        try {
          const document = await createClinicalDocumentFromText(patientId, {
            title,
            rawText: queuedNote.rawText,
            documentType: queuedNote.documentType,
          })
          documentId = document.id
        } catch (caughtError) {
          setFailedItemLabel(title)
          throw caughtError
        }

        uploadedIds.current.set(key, documentId)
        clinicalDocumentIds.push(documentId)
      }

      return clinicalDocumentIds
    },
    [patientId],
  )

  const submit = useCallback(
    async ({ files, notes, existingDocumentIds = [] }: SubmitInput): Promise<number> => {
      setIsSubmitting(true)
      setError(null)
      setFailedItemLabel(null)

      try {
        const uploadedDocumentIds = await uploadQueuedItems(files, notes)
        const result = await createAnalysisFromDocuments(patientId, [
          ...existingDocumentIds,
          ...uploadedDocumentIds,
        ])

        uploadedIds.current.clear()

        return result.analysis_id
      } catch (caughtError) {
        setError((caughtError as ApiError).message)
        throw caughtError
      } finally {
        setIsSubmitting(false)
      }
    },
    [patientId, uploadQueuedItems],
  )

  const saveDocuments = useCallback(
    async ({ files, notes }: SaveInput): Promise<number[]> => {
      setIsSubmitting(true)
      setError(null)
      setFailedItemLabel(null)

      try {
        const documentIds = await uploadQueuedItems(files, notes)

        uploadedIds.current.clear()

        return documentIds
      } catch (caughtError) {
        setError((caughtError as ApiError).message)
        throw caughtError
      } finally {
        setIsSubmitting(false)
      }
    },
    [uploadQueuedItems],
  )

  return { isSubmitting, error, failedItemLabel, submit, saveDocuments, invalidateItem }
}
