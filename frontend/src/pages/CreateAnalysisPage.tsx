import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { FormError } from '@/components/common/FormError'
import { PatientPageNav } from '@/components/patients/PatientPageNav'
import { EmptyDocumentsState } from '@/components/documents/EmptyDocumentsState'
import { filterClinicalDocuments } from '@/components/documents/filterClinicalDocuments'
import { FileDropzone } from '@/components/upload/FileDropzone'
import { UploadedFileList } from '@/components/upload/UploadedFileList'
import { ManualNoteEditor } from '@/components/upload/ManualNoteEditor'
import { NoteCard } from '@/components/upload/NoteCard'
import { usePatient } from '@/hooks/usePatient'
import { usePatientClinicalDocuments } from '@/hooks/usePatientClinicalDocuments'
import { useDocumentQueue } from '@/hooks/useDocumentQueue'
import { documentTypeLabel } from '@/api/clinicalDocuments'
import { analysisProcessingPath, patientDetailPath } from '@/routes/paths'

// Existing Documents shows this many at a time before "Show more" is needed -
// a patient with a long document history shouldn't dump dozens of checkboxes
// onto the page at once.
const EXISTING_DOCUMENTS_PREVIEW_LIMIT = 3

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

export function CreateAnalysisPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)
  const navigate = useNavigate()

  const {
    patient,
    isLoading: isPatientLoading,
    error: patientError,
    retry: retryPatient,
  } = usePatient(id)
  const {
    documents,
    isLoading: areDocumentsLoading,
    error: documentsError,
    retry: retryDocuments,
  } = usePatientClinicalDocuments(id)

  const [selectedExistingIds, setSelectedExistingIds] = useState<Set<number>>(new Set())
  const [existingDocumentsQuery, setExistingDocumentsQuery] = useState('')
  const [showAllExisting, setShowAllExisting] = useState(false)
  const {
    files,
    notes,
    fileError,
    totalCount: queuedCount,
    handleFilesSelected,
    handleRemoveFile,
    handleFileDocumentTypeChange,
    handleFileTitleChange,
    handleAddNote,
    handleUpdateNote,
    handleRemoveNote,
  } = useDocumentQueue()

  const totalSelectedCount = selectedExistingIds.size + queuedCount

  function handleExistingDocumentsQueryChange(value: string) {
    setExistingDocumentsQuery(value)
    // A new search should always start collapsed; showing every match right
    // away for a broad query would recreate the same content overload
    // Show more exists to avoid.
    setShowAllExisting(false)
  }

  function toggleExistingDocument(documentId: number) {
    setSelectedExistingIds((current) => {
      const next = new Set(current)

      if (next.has(documentId)) {
        next.delete(documentId)
      } else {
        next.add(documentId)
      }

      return next
    })
  }

  function handleCreateAnalysis() {
    if (totalSelectedCount === 0) return

    navigate(analysisProcessingPath(id), {
      state: { files, notes, existingDocumentIds: Array.from(selectedExistingIds) },
    })
  }

  if (isPatientLoading) {
    return <LoadingSpinner label="Loading patient" />
  }

  if (patientError || !patient) {
    return (
      <ErrorState
        title="Couldn't load this patient"
        message={patientError ?? 'Patient not found.'}
        onRetry={retryPatient}
      />
    )
  }

  const selectedExistingDocuments = documents.filter((document) =>
    selectedExistingIds.has(document.id),
  )

  const filteredExistingDocuments = filterClinicalDocuments(documents, existingDocumentsQuery)
  const visibleExistingDocuments = showAllExisting
    ? filteredExistingDocuments
    : filteredExistingDocuments.slice(0, EXISTING_DOCUMENTS_PREVIEW_LIMIT)
  const hiddenExistingDocumentsCount =
    filteredExistingDocuments.length - visibleExistingDocuments.length

  return (
    <div className="flex flex-col gap-8">
      <PatientPageNav
        patient={patient}
        trail={[{ label: 'Create Analysis' }]}
        backTo={patientDetailPath(patient.id)}
        backLabel={`${patient.first_name} ${patient.last_name}`}
      />

      <PageHeader
        title="Create Analysis"
        description={`Build an analysis for ${patient.first_name} ${patient.last_name} from any combination of existing and newly uploaded documents.`}
      />

      <section aria-labelledby="existing-documents-heading" className="flex flex-col gap-4">
        <h2 id="existing-documents-heading" className="text-lg font-semibold text-foreground">
          Existing Documents
        </h2>

        {areDocumentsLoading && <LoadingSpinner label="Loading documents" />}

        {!areDocumentsLoading && documentsError && (
          <ErrorState
            title="Couldn't load documents"
            message={documentsError}
            onRetry={retryDocuments}
          />
        )}

        {!areDocumentsLoading && !documentsError && documents.length === 0 && (
          <EmptyDocumentsState patientId={patient.id} />
        )}

        {!areDocumentsLoading && !documentsError && documents.length > 0 && (
          <>
            <Input
              type="search"
              label="Search existing documents"
              value={existingDocumentsQuery}
              onChange={(event) => handleExistingDocumentsQueryChange(event.target.value)}
              placeholder="Search by title or document type"
              className="sm:max-w-xs"
            />

            {filteredExistingDocuments.length === 0 ? (
              <p className="text-sm text-muted">No documents match your search.</p>
            ) : (
              <>
                <ul className="flex flex-col gap-3">
                  {visibleExistingDocuments.map((document) => {
                    const isSelected = selectedExistingIds.has(document.id)

                    return (
                      <li key={document.id}>
                        <label
                          className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 shadow-sm hover:bg-surface-hover ${
                            isSelected ? 'border-primary/60 bg-info/10' : 'border-border bg-surface'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleExistingDocument(document.id)}
                            className="mt-1 h-4 w-4 cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
                          />
                          <span className="flex min-w-0 flex-col gap-0.5">
                            <span className="text-sm font-semibold break-words text-foreground">
                              {document.title}
                            </span>{' '}
                            <span className="text-xs text-muted">
                              {documentTypeLabel(document.document_type)} · Uploaded{' '}
                              {formatDate(document.created_at)}
                            </span>
                          </span>
                        </label>
                      </li>
                    )
                  })}
                </ul>

                {hiddenExistingDocumentsCount > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowAllExisting(true)}
                    className="self-start rounded-md px-2 py-1 text-sm font-medium text-link hover:bg-primary/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
                  >
                    Show {hiddenExistingDocumentsCount} more
                  </button>
                )}

                {showAllExisting &&
                  filteredExistingDocuments.length > EXISTING_DOCUMENTS_PREVIEW_LIMIT && (
                    <button
                      type="button"
                      onClick={() => setShowAllExisting(false)}
                      className="self-start rounded-md px-2 py-1 text-sm font-medium text-muted hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
                    >
                      Show less
                    </button>
                  )}
              </>
            )}
          </>
        )}
      </section>

      <section aria-labelledby="upload-additional-heading" className="flex flex-col gap-4">
        <h2 id="upload-additional-heading" className="text-lg font-semibold text-foreground">
          Upload Additional Documents
        </h2>

        <FileDropzone
          onFilesSelected={handleFilesSelected}
          errorId={fileError ? 'create-analysis-file-error' : undefined}
        />
        {fileError && <FormError id="create-analysis-file-error" message={fileError} />}
        <UploadedFileList
          files={files}
          onRemove={handleRemoveFile}
          onDocumentTypeChange={handleFileDocumentTypeChange}
          onTitleChange={handleFileTitleChange}
          existingDocumentTitles={documents.map((document) => document.title)}
        />
        <ManualNoteEditor onAdd={handleAddNote} />
      </section>

      <section aria-labelledby="selected-documents-heading" className="flex flex-col gap-4">
        <h2
          id="selected-documents-heading"
          aria-live="polite"
          className="text-lg font-semibold text-foreground"
        >
          Selected Documents ({totalSelectedCount})
        </h2>

        {totalSelectedCount === 0 && (
          <p className="text-sm text-muted">
            No documents selected yet. Check an existing document above, or upload a new one.
          </p>
        )}

        {totalSelectedCount > 0 && selectedExistingDocuments.length === 0 && notes.length === 0 && (
          <p className="text-sm text-muted">
            Uploaded files are listed above, in Upload Additional Documents.
          </p>
        )}

        {(selectedExistingDocuments.length > 0 || notes.length > 0) && (
          <div className="flex flex-col gap-4">
            {selectedExistingDocuments.length > 0 && (
              <ul className="flex flex-col gap-2">
                {selectedExistingDocuments.map((document) => (
                  <li
                    key={document.id}
                    className="flex flex-col gap-2 rounded-md border border-border bg-surface px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between"
                  >
                    <span className="min-w-0 break-words">
                      <span className="font-medium text-foreground">{document.title}</span>{' '}
                      <span className="text-xs text-muted">
                        ({documentTypeLabel(document.document_type)}, already on file)
                      </span>
                    </span>
                    <button
                      type="button"
                      onClick={() => toggleExistingDocument(document.id)}
                      aria-label={`Remove ${document.title} from selection`}
                      className="self-start rounded-md px-2 py-1 text-xs font-medium text-danger hover:bg-danger/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring sm:self-auto"
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}

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
          </div>
        )}
      </section>

      <div className="flex flex-wrap items-center gap-4">
        <Button onClick={handleCreateAnalysis} disabled={totalSelectedCount === 0}>
          Create Analysis
        </Button>
        <Link
          to={patientDetailPath(patient.id)}
          replace
          className="text-sm text-danger hover:underline"
        >
          Cancel
        </Link>
      </div>
    </div>
  )
}
