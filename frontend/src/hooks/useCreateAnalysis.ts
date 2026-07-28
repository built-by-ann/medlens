import { useCallback, useRef, useState } from 'react'
import { createClinicalDocumentFromText, uploadClinicalDocumentFile } from '@/api/clinicalDocuments'
import { createAnalysisFromDocuments } from '@/api/analyses'
import type { ApiError } from '@/api/client'

export interface QueuedFile {
  id: number
  file: File
  documentType: string
}

export interface QueuedNote {
  id: number
  title: string
  rawText: string
  documentType: string
}

interface SubmitInput {
  files: QueuedFile[]
  notes: QueuedNote[]
}

interface UseCreateAnalysisResult {
  isSubmitting: boolean
  error: string | null
  failedItemLabel: string | null
  submit: (input: SubmitInput) => Promise<number>
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
 * creates an analysis from all of them.
 *
 * Each item's resulting document id is cached as soon as it succeeds,
 * keyed by its stable queue id (fileItemKey/noteItemKey), not its position.
 * If a later item then fails, the queue up to that point has already been
 * cached, so calling submit() again with the same queue reuses those ids
 * instead of re-uploading them, retrying only what didn't already succeed.
 * The cache is owned here, not in UploadPage's state, since it is
 * meaningless outside a submission attempt: UploadPage only ever needs to
 * invalidate an entry (when the user edits or removes the associated item,
 * since a cached id would otherwise silently refer to stale content), never
 * read or persist it. It is also cleared automatically once an analysis is
 * actually created, since a new submission afterwards is a new attempt.
 */
export function useCreateAnalysis(): UseCreateAnalysisResult {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [failedItemLabel, setFailedItemLabel] = useState<string | null>(null)
  const uploadedIds = useRef(new Map<string, number>())

  const invalidateItem = useCallback((key: string) => {
    uploadedIds.current.delete(key)
  }, [])

  const submit = useCallback(async ({ files, notes }: SubmitInput): Promise<number> => {
    setIsSubmitting(true)
    setError(null)
    setFailedItemLabel(null)

    try {
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
            queuedFile.file,
            queuedFile.documentType,
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
          const document = await createClinicalDocumentFromText({
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

      const result = await createAnalysisFromDocuments(clinicalDocumentIds)

      uploadedIds.current.clear()

      return result.analysis_id
    } catch (caughtError) {
      setError((caughtError as ApiError).message)
      throw caughtError
    } finally {
      setIsSubmitting(false)
    }
  }, [])

  return { isSubmitting, error, failedItemLabel, submit, invalidateItem }
}
