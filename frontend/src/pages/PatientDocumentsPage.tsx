import { Link, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { PatientPageNav } from '@/components/patients/PatientPageNav'
import { ClinicalDocumentList } from '@/components/documents/ClinicalDocumentList'
import { EmptyDocumentsState } from '@/components/documents/EmptyDocumentsState'
import { usePatient } from '@/hooks/usePatient'
import { usePatientClinicalDocuments } from '@/hooks/usePatientClinicalDocuments'
import { createAnalysisPath, patientDetailPath, patientUploadPath } from '@/routes/paths'

export function PatientDocumentsPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)

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
    removeDocument,
  } = usePatientClinicalDocuments(id)

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

  return (
    <div className="flex flex-col gap-8">
      <PatientPageNav
        patient={patient}
        trail={[{ label: 'Clinical Documents' }]}
        backTo={patientDetailPath(patient.id)}
        backLabel={`${patient.first_name} ${patient.last_name}`}
      />

      <PageHeader
        title="Clinical Documents"
        description={`Complete document history for ${patient.first_name} ${patient.last_name}`}
      />

      <nav aria-label="Document actions" className="flex flex-wrap gap-2">
        <Link
          to={patientUploadPath(patient.id)}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        >
          Upload Documents
        </Link>
        <Link
          to={createAnalysisPath(patient.id)}
          className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        >
          Create Analysis
        </Link>
        <Link
          to={patientDetailPath(patient.id)}
          className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        >
          View Patient
        </Link>
      </nav>

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
        <ClinicalDocumentList documents={documents} onDelete={removeDocument} />
      )}
    </div>
  )
}
