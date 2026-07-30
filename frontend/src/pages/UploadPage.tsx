import { useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { Button } from '@/components/common/Button'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { PatientPageNav } from '@/components/patients/PatientPageNav'
import { FileDropzone } from '@/components/upload/FileDropzone'
import { UploadedFileList } from '@/components/upload/UploadedFileList'
import { ManualNoteEditor } from '@/components/upload/ManualNoteEditor'
import { NoteCard, type DraftNote } from '@/components/upload/NoteCard'
import { UploadEmptyState } from '@/components/upload/UploadEmptyState'
import { useCreateAnalysis, type QueuedFile } from '@/hooks/useCreateAnalysis'
import { usePatient } from '@/hooks/usePatient'
import {
  isSupportedFileType,
  SUPPORTED_FILE_EXTENSIONS,
  DEFAULT_DOCUMENT_TYPE,
} from '@/api/clinicalDocuments'
import { analysisProcessingPath, patientDetailPath, patientDocumentsPath } from '@/routes/paths'

function isDuplicateFile(existing: QueuedFile[], candidate: File): boolean {
  return existing.some(
    (queued) => queued.file.name === candidate.name && queued.file.size === candidate.size,
  )
}

export function UploadPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)
  const navigate = useNavigate()
  const { patient, isLoading: isPatientLoading, error: patientError, retry } = usePatient(id)
  const nextFileId = useRef(0)
  const nextNoteId = useRef(0)
  const { isSubmitting: isSaving, error: saveError, saveDocuments } = useCreateAnalysis(id)

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

  function handleSubmit() {
    if (totalCount === 0) {
      setValidationMessage('Add at least one file or note before starting an analysis.')
      return
    }

    setValidationMessage(null)
    navigate(analysisProcessingPath(id), { state: { files, notes } })
  }

  async function handleSave() {
    if (totalCount === 0) {
      setValidationMessage('Add at least one file or note before saving.')
      return
    }

    setValidationMessage(null)
    try {
      await saveDocuments({ files, notes })
      navigate(patientDocumentsPath(id))
    } catch {
      // saveError already reflects this via the hook's own state.
    }
  }

  if (isPatientLoading) {
    return <LoadingSpinner label="Loading patient" />
  }

  if (patientError || !patient) {
    return (
      <ErrorState
        title="Couldn't load this patient"
        message={patientError ?? 'Patient not found.'}
        onRetry={retry}
      />
    )
  }

  return (
    <div className="flex flex-col gap-8">
      <PatientPageNav
        patient={patient}
        trail={[{ label: 'Upload' }]}
        backTo={patientDetailPath(patient.id)}
        backLabel={`${patient.first_name} ${patient.last_name}`}
      />

      <PageHeader
        title={`Upload documents for ${patient.first_name} ${patient.last_name}`}
        description="Add one or more clinical notes. MedLens extracts medications from what you provide and flags any discrepancies against this patient's medication list."
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

      {saveError && (
        <p role="alert" className="text-sm text-red-600">
          {saveError}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={handleSubmit} disabled={isSaving}>
          Start Analysis
        </Button>
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={isSaving}
          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSaving ? 'Saving...' : 'Save documents'}
        </button>
      </div>
    </div>
  )
}
