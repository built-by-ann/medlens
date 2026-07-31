import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { FormError } from '@/components/common/FormError'
import { PatientPageNav } from '@/components/patients/PatientPageNav'
import { FileDropzone } from '@/components/upload/FileDropzone'
import { UploadedFileList } from '@/components/upload/UploadedFileList'
import { ManualNoteEditor } from '@/components/upload/ManualNoteEditor'
import { NoteCard } from '@/components/upload/NoteCard'
import { UploadEmptyState } from '@/components/upload/UploadEmptyState'
import { useCreateAnalysis } from '@/hooks/useCreateAnalysis'
import { useDocumentQueue } from '@/hooks/useDocumentQueue'
import { usePatient } from '@/hooks/usePatient'
import { patientDetailPath, patientDocumentsPath } from '@/routes/paths'

export function UploadPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)
  const navigate = useNavigate()
  const { patient, isLoading: isPatientLoading, error: patientError, retry } = usePatient(id)
  const {
    isSubmitting: isSaving,
    error: saveError,
    failedItemLabel,
    saveDocuments,
  } = useCreateAnalysis(id)

  const {
    files,
    notes,
    fileError,
    totalCount,
    handleFilesSelected,
    handleRemoveFile,
    handleFileDocumentTypeChange,
    handleFileTitleChange,
    handleAddNote,
    handleUpdateNote,
    handleRemoveNote,
  } = useDocumentQueue()

  const [validationMessage, setValidationMessage] = useState<string | null>(null)

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

  // Names which file/note failed to upload, when known, so a batch of
  // several items doesn't leave the user guessing which one needs fixing.
  const saveErrorMessage = saveError
    ? failedItemLabel
      ? `${failedItemLabel}: ${saveError}`
      : saveError
    : null

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
        description="Add clinical documents to this patient's record. Once saved, build an analysis from any combination of documents via Create Analysis."
      />

      <section aria-labelledby="file-upload-heading" className="flex flex-col gap-4">
        <h2 id="file-upload-heading" className="text-lg font-semibold text-slate-900">
          Upload files
        </h2>
        <FileDropzone
          onFilesSelected={handleFilesSelected}
          errorId={fileError ? 'upload-file-error' : undefined}
        />
        {fileError && <FormError id="upload-file-error" message={fileError} />}
        <UploadedFileList
          files={files}
          onRemove={handleRemoveFile}
          onDocumentTypeChange={handleFileDocumentTypeChange}
          onTitleChange={handleFileTitleChange}
        />
      </section>

      <section aria-labelledby="manual-entry-heading" className="flex flex-col gap-4">
        <h2 id="manual-entry-heading" className="text-lg font-semibold text-slate-900">
          Paste note text
        </h2>
        {notes.length > 0 && (
          <ul className="flex flex-col gap-3">
            {notes.map((note, index) => (
              <li key={note.id}>
                <NoteCard
                  note={note}
                  position={index + 1}
                  onUpdate={handleUpdateNote}
                  onRemove={handleRemoveNote}
                />
              </li>
            ))}
          </ul>
        )}
        <ManualNoteEditor onAdd={handleAddNote} />
      </section>

      {totalCount === 0 && <UploadEmptyState />}

      {validationMessage && <FormError message={validationMessage} />}

      {saveErrorMessage && <FormError message={saveErrorMessage} />}

      <div>
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={isSaving}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSaving ? 'Saving...' : 'Save documents'}
        </button>
      </div>
    </div>
  )
}
