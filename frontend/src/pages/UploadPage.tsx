import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { Button } from '@/components/common/Button'
import { FileDropzone } from '@/components/upload/FileDropzone'
import { UploadedFileList } from '@/components/upload/UploadedFileList'
import { ManualNoteEditor } from '@/components/upload/ManualNoteEditor'
import { NoteCard, type DraftNote } from '@/components/upload/NoteCard'
import { UploadEmptyState } from '@/components/upload/UploadEmptyState'
import {
  useCreateAnalysis,
  fileItemKey,
  noteItemKey,
  type QueuedFile,
} from '@/hooks/useCreateAnalysis'
import {
  isSupportedFileType,
  SUPPORTED_FILE_EXTENSIONS,
  DEFAULT_DOCUMENT_TYPE,
} from '@/api/clinicalDocuments'
import { analysisDetailPath } from '@/routes/paths'

function isDuplicateFile(existing: QueuedFile[], candidate: File): boolean {
  return existing.some(
    (queued) => queued.file.name === candidate.name && queued.file.size === candidate.size,
  )
}

export function UploadPage() {
  const navigate = useNavigate()
  const { isSubmitting, error, failedItemLabel, submit, invalidateItem } = useCreateAnalysis()
  const nextFileId = useRef(0)
  const nextNoteId = useRef(0)

  const [files, setFiles] = useState<QueuedFile[]>([])
  const [notes, setNotes] = useState<DraftNote[]>([])
  const [fileError, setFileError] = useState<string | null>(null)
  const [validationMessage, setValidationMessage] = useState<string | null>(null)

  const totalCount = files.length + notes.length

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
    invalidateItem(fileItemKey(id))
    setFiles((current) => current.filter((queued) => queued.id !== id))
  }

  function handleFileDocumentTypeChange(id: number, documentType: string) {
    invalidateItem(fileItemKey(id))
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
    invalidateItem(noteItemKey(id))
    setNotes((current) =>
      current.map((existing) => (existing.id === id ? { ...existing, ...note } : existing)),
    )
  }

  function handleRemoveNote(id: number) {
    invalidateItem(noteItemKey(id))
    setNotes((current) => current.filter((existing) => existing.id !== id))
  }

  async function handleSubmit() {
    if (isSubmitting) {
      return
    }

    if (totalCount === 0) {
      setValidationMessage('Add at least one file or note before starting an analysis.')
      return
    }

    setValidationMessage(null)

    try {
      const analysisId = await submit({ files, notes })
      navigate(analysisDetailPath(analysisId))
    } catch {
      // error / failedItemLabel are already reflected below via hook state.
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Upload documents"
        description="Add one or more clinical notes. MedLens extracts medications from what you provide and flags any discrepancies against your medication list."
      />

      <section aria-labelledby="file-upload-heading" className="flex flex-col gap-4">
        <h2 id="file-upload-heading" className="text-lg font-semibold text-slate-900">
          Upload files
        </h2>
        <FileDropzone onFilesSelected={handleFilesSelected} />
        {fileError && (
          <p role="alert" className="text-sm text-red-600">
            {fileError}
          </p>
        )}
        <UploadedFileList
          files={files}
          onRemove={handleRemoveFile}
          onDocumentTypeChange={handleFileDocumentTypeChange}
        />
      </section>

      <section aria-labelledby="manual-entry-heading" className="flex flex-col gap-4">
        <h2 id="manual-entry-heading" className="text-lg font-semibold text-slate-900">
          Paste note text
        </h2>
        {notes.length > 0 && (
          <ul className="flex flex-col gap-3">
            {notes.map((note) => (
              <li key={note.id}>
                <NoteCard note={note} onUpdate={handleUpdateNote} onRemove={handleRemoveNote} />
              </li>
            ))}
          </ul>
        )}
        <ManualNoteEditor onAdd={handleAddNote} />
      </section>

      {totalCount === 0 && <UploadEmptyState />}

      {validationMessage && (
        <p role="alert" className="text-sm text-red-600">
          {validationMessage}
        </p>
      )}

      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
          {failedItemLabel && ` (${failedItemLabel})`}
        </p>
      )}

      <div>
        <Button onClick={handleSubmit} disabled={isSubmitting}>
          {isSubmitting ? 'Starting analysis...' : 'Start Analysis'}
        </Button>
      </div>
    </div>
  )
}
