import { useRef, useState } from 'react'
import type { DraftNote } from '@/components/upload/NoteCard'
import type { QueuedFile } from '@/hooks/useCreateAnalysis'
import { isDuplicateFile } from '@/utils/queuedFiles'
import {
  isSupportedFileType,
  SUPPORTED_FILE_EXTENSIONS,
  DEFAULT_DOCUMENT_TYPE,
} from '@/api/clinicalDocuments'

interface UseDocumentQueueResult {
  files: QueuedFile[]
  notes: DraftNote[]
  fileError: string | null
  totalCount: number
  handleFilesSelected: (selected: File[]) => void
  handleRemoveFile: (id: number) => void
  handleFileDocumentTypeChange: (id: number, documentType: string) => void
  handleAddNote: (note: { title: string; rawText: string; documentType: string }) => void
  handleUpdateNote: (
    id: number,
    note: { title: string; rawText: string; documentType: string },
  ) => void
  handleRemoveNote: (id: number) => void
}

/**
 * Local, not-yet-persisted queue of files and pasted notes, shared by every
 * page that lets a provider stage clinical documents before they become
 * real ClinicalDocuments (UploadPage's "Save documents," and Issue #160's
 * unified CreateAnalysisPage) - extracted so the two pages can't drift
 * apart on file-type validation, de-duplication, or edit/remove behavior.
 * Owns no network calls itself; callers decide what to do with the queue
 * (saveDocuments vs. navigating into analysis creation).
 */
export function useDocumentQueue(): UseDocumentQueueResult {
  const nextFileId = useRef(0)
  const nextNoteId = useRef(0)

  const [files, setFiles] = useState<QueuedFile[]>([])
  const [notes, setNotes] = useState<DraftNote[]>([])
  const [fileError, setFileError] = useState<string | null>(null)

  function handleFilesSelected(selected: File[]) {
    const unsupported = selected.filter((file) => !isSupportedFileType(file))

    if (unsupported.length > 0) {
      const names = unsupported.map((file) => file.name).join(', ')
      setFileError(
        `${names} ${unsupported.length === 1 ? 'is not a supported file type' : 'are not supported file types'}. Supported formats: ${SUPPORTED_FILE_EXTENSIONS.join(', ')}.`,
      )
    } else {
      setFileError(null)
    }

    const supported = selected.filter((file) => isSupportedFileType(file))

    setFiles((current) => [
      ...current,
      ...supported
        .filter((file) => !isDuplicateFile(current, file))
        .map((file) => ({ id: nextFileId.current++, file, documentType: DEFAULT_DOCUMENT_TYPE })),
    ])
  }

  function handleRemoveFile(id: number) {
    setFiles((current) => current.filter((queued) => queued.id !== id))
  }

  function handleFileDocumentTypeChange(id: number, documentType: string) {
    setFiles((current) =>
      current.map((queued) => (queued.id === id ? { ...queued, documentType } : queued)),
    )
  }

  function handleAddNote(note: { title: string; rawText: string; documentType: string }) {
    setNotes((current) => [...current, { id: nextNoteId.current++, ...note }])
  }

  function handleUpdateNote(
    id: number,
    note: { title: string; rawText: string; documentType: string },
  ) {
    setNotes((current) =>
      current.map((existing) => (existing.id === id ? { ...existing, ...note } : existing)),
    )
  }

  function handleRemoveNote(id: number) {
    setNotes((current) => current.filter((existing) => existing.id !== id))
  }

  return {
    files,
    notes,
    fileError,
    totalCount: files.length + notes.length,
    handleFilesSelected,
    handleRemoveFile,
    handleFileDocumentTypeChange,
    handleAddNote,
    handleUpdateNote,
    handleRemoveNote,
  }
}
