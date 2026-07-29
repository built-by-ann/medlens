import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { Button } from '@/components/common/Button'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { PatientBreadcrumb } from '@/components/patients/PatientBreadcrumb'
import { EmptyDocumentsState } from '@/components/documents/EmptyDocumentsState'
import { usePatient } from '@/hooks/usePatient'
import { usePatientClinicalDocuments } from '@/hooks/usePatientClinicalDocuments'
import { documentTypeLabel } from '@/api/clinicalDocuments'
import { analysisProcessingPath, patientDetailPath } from '@/routes/paths'

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

export function SelectDocumentsPage() {
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

  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())

  function toggleDocument(documentId: number) {
    setSelectedIds((current) => {
      const next = new Set(current)

      if (next.has(documentId)) {
        next.delete(documentId)
      } else {
        next.add(documentId)
      }

      return next
    })
  }

  function handleSubmit() {
    if (selectedIds.size === 0) return

    navigate(analysisProcessingPath(id), {
      state: { files: [], notes: [], existingDocumentIds: Array.from(selectedIds) },
    })
  }

  if (isPatientLoading || areDocumentsLoading) {
    return <LoadingSpinner label="Loading documents" />
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

  if (documentsError) {
    return (
      <ErrorState
        title="Couldn't load documents"
        message={documentsError}
        onRetry={retryDocuments}
      />
    )
  }

  return (
    <div className="flex flex-col gap-8">
      <PatientBreadcrumb patient={patient} trail={[{ label: 'Select documents' }]} />

      <PageHeader
        title="Select existing documents"
        description={`Choose one or more of ${patient.first_name} ${patient.last_name}'s previously uploaded documents to analyze - no need to upload them again.`}
      />

      <Link
        to={patientDetailPath(patient.id)}
        className="self-start text-sm text-slate-600 hover:underline"
      >
        ← Back to {patient.first_name} {patient.last_name}
      </Link>

      {documents.length === 0 ? (
        <EmptyDocumentsState patientId={patient.id} />
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {documents.map((document) => {
              const isSelected = selectedIds.has(document.id)

              return (
                <li key={document.id}>
                  <label
                    className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 shadow-sm hover:bg-slate-50 ${
                      isSelected ? 'border-blue-400 bg-blue-50' : 'border-slate-200 bg-white'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleDocument(document.id)}
                      className="mt-1 h-4 w-4 cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                    />
                    <span className="flex flex-col gap-0.5">
                      <span className="text-sm font-semibold text-slate-900">{document.title}</span>
                      <span className="text-xs text-slate-500">
                        {documentTypeLabel(document.document_type)} · Uploaded{' '}
                        {formatDate(document.created_at)}
                      </span>
                    </span>
                  </label>
                </li>
              )
            })}
          </ul>

          <div className="flex flex-wrap items-center gap-4">
            <Button onClick={handleSubmit} disabled={selectedIds.size === 0}>
              Create Analysis
            </Button>
            <p aria-live="polite" className="text-sm text-slate-600">
              {selectedIds.size} of {documents.length} document{documents.length === 1 ? '' : 's'}{' '}
              selected
            </p>
          </div>
        </>
      )}
    </div>
  )
}
