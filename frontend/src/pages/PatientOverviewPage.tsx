import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { PatientDetails } from '@/components/patients/PatientDetails'
import { PatientPageNav } from '@/components/patients/PatientPageNav'
import { ArchivePatientDialog } from '@/components/patients/ArchivePatientDialog'
import { MedicationList } from '@/components/medications/MedicationList'
import { EmptyMedicationState } from '@/components/medications/EmptyMedicationState'
import { RecentDocumentsList } from '@/components/documents/RecentDocumentsList'
import { EmptyDocumentsState } from '@/components/documents/EmptyDocumentsState'
import { RecentAnalysesList } from '@/components/analyses/RecentAnalysesList'
import { AnalysesEmptyState } from '@/components/analyses/AnalysesEmptyState'
import { usePatient } from '@/hooks/usePatient'
import { usePatientMedications } from '@/hooks/usePatientMedications'
import { usePatientClinicalDocuments } from '@/hooks/usePatientClinicalDocuments'
import { usePatientAnalyses } from '@/hooks/usePatientAnalyses'
import { archivePatient } from '@/api/patients'
import {
  ROUTES,
  createAnalysisPath,
  patientAnalysesPath,
  patientDocumentsPath,
  patientEditPath,
  patientMedicationsPath,
  patientUploadPath,
} from '@/routes/paths'
import type { ApiError } from '@/api/client'

// Recent Analyses on the Overview page is a glance-and-go preview, not the
// full browsable history (that's PatientAnalysesPage) - a small limit keeps
// this page from growing unbounded as a patient accumulates analyses over
// time.
const RECENT_ANALYSES_PREVIEW_LIMIT = 3

// Recent Clinical Documents is the same kind of glance-and-go preview,
// pointing at the full history on PatientDocumentsPage (Issue #146). The
// backend's clinical-documents list endpoint has no limit query param (see
// docs/api.md), so this is applied client-side against the same full list
// usePatientClinicalDocuments already fetches, rather than a backend change.
const RECENT_DOCUMENTS_PREVIEW_LIMIT = 3

export function PatientOverviewPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const navigate = useNavigate()
  const id = Number(patientId)
  const { patient, isLoading, error, retry } = usePatient(id)
  const {
    medications,
    isLoading: areMedicationsLoading,
    error: medicationsError,
    retry: retryMedications,
    editMedication,
    removeMedication,
  } = usePatientMedications(id)
  const {
    documents,
    isLoading: areDocumentsLoading,
    error: documentsError,
    retry: retryDocuments,
  } = usePatientClinicalDocuments(id)
  const {
    analyses,
    isLoading: areAnalysesLoading,
    error: analysesError,
    retry: retryAnalyses,
  } = usePatientAnalyses(id, RECENT_ANALYSES_PREVIEW_LIMIT)

  const [isConfirmingArchive, setIsConfirmingArchive] = useState(false)
  const [isArchiving, setIsArchiving] = useState(false)
  const [archiveError, setArchiveError] = useState<string | null>(null)

  function closeArchiveDialog() {
    if (isArchiving) return
    setIsConfirmingArchive(false)
    setArchiveError(null)
  }

  async function handleConfirmArchive() {
    if (isArchiving) return

    setIsArchiving(true)
    setArchiveError(null)
    try {
      await archivePatient(id)
      navigate(ROUTES.patients)
    } catch (caughtError) {
      setArchiveError((caughtError as ApiError).message)
      setIsArchiving(false)
    }
  }

  return (
    <div className="flex flex-col gap-8">
      {isLoading && <LoadingSpinner label="Loading patient" />}

      {!isLoading && error && (
        <ErrorState title="Couldn't load this patient" message={error} onRetry={retry} />
      )}

      {!isLoading && !error && patient && (
        <>
          <PatientPageNav patient={patient} backTo={ROUTES.patients} backLabel="Patients" />

          <PageHeader
            title={`${patient.first_name} ${patient.last_name}`}
            description="Patient overview"
            actions={
              <div className="flex flex-wrap gap-2">
                <Link
                  to={patientEditPath(patient.id)}
                  className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
                >
                  Edit
                </Link>
                <button
                  type="button"
                  onClick={() => setIsConfirmingArchive(true)}
                  className="rounded-md border border-danger px-4 py-2 text-sm font-medium text-danger hover:bg-danger/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
                >
                  Archive
                </button>
              </div>
            }
          />

          <PatientDetails patient={patient} />

          <nav aria-label="Quick actions" className="flex flex-wrap gap-2">
            <Link
              to={createAnalysisPath(patient.id)}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
            >
              Create Analysis
            </Link>
            <Link
              to={patientUploadPath(patient.id)}
              className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
            >
              Upload document
            </Link>
            <Link
              to={patientMedicationsPath(patient.id)}
              className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
            >
              Manage medications
            </Link>
          </nav>

          <section aria-labelledby="documents-heading" className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 id="documents-heading" className="text-lg font-semibold text-foreground">
                Recent clinical documents
              </h2>
              {documents.length > 0 && (
                <Link
                  to={patientDocumentsPath(patient.id)}
                  aria-label="View all clinical documents"
                  className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
                >
                  View All
                </Link>
              )}
            </div>

            {areDocumentsLoading && <LoadingSpinner label="Loading documents" />}

            {!areDocumentsLoading && documentsError && (
              <ErrorState
                title="Couldn't load clinical documents"
                message={documentsError}
                onRetry={retryDocuments}
              />
            )}

            {!areDocumentsLoading && !documentsError && documents.length === 0 && (
              <EmptyDocumentsState patientId={patient.id} />
            )}

            {!areDocumentsLoading && !documentsError && documents.length > 0 && (
              <RecentDocumentsList documents={documents.slice(0, RECENT_DOCUMENTS_PREVIEW_LIMIT)} />
            )}
          </section>

          <section aria-labelledby="recent-analyses-heading" className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 id="recent-analyses-heading" className="text-lg font-semibold text-foreground">
                Recent analyses
              </h2>
              {analyses.length > 0 && (
                <Link
                  to={patientAnalysesPath(patient.id)}
                  aria-label="View all analyses"
                  className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
                >
                  View All
                </Link>
              )}
            </div>

            {areAnalysesLoading && <LoadingSpinner label="Loading analyses" />}

            {!areAnalysesLoading && analysesError && (
              <ErrorState
                title="Couldn't load analyses"
                message={analysesError}
                onRetry={retryAnalyses}
              />
            )}

            {!areAnalysesLoading && !analysesError && analyses.length === 0 && (
              <AnalysesEmptyState patientId={patient.id} />
            )}

            {!areAnalysesLoading && !analysesError && analyses.length > 0 && (
              <RecentAnalysesList analyses={analyses} />
            )}
          </section>

          <section aria-labelledby="medications-heading" className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 id="medications-heading" className="text-lg font-semibold text-foreground">
                Medications
              </h2>
              {medications.length > 0 && (
                <Link
                  to={patientMedicationsPath(patient.id)}
                  aria-label="View all medications"
                  className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
                >
                  View All
                </Link>
              )}
            </div>

            {areMedicationsLoading && <LoadingSpinner label="Loading medications" />}

            {!areMedicationsLoading && medicationsError && (
              <ErrorState
                title="Couldn't load medications"
                message={medicationsError}
                onRetry={retryMedications}
              />
            )}

            {!areMedicationsLoading && !medicationsError && medications.length === 0 && (
              <EmptyMedicationState
                message="Keep this patient's medication list up to date so MedLens can compare it against their clinical documents."
                addMedicationHref={patientMedicationsPath(patient.id)}
              />
            )}

            {!areMedicationsLoading && !medicationsError && medications.length > 0 && (
              <MedicationList
                medications={medications}
                onEdit={editMedication}
                onDelete={removeMedication}
              />
            )}
          </section>
        </>
      )}

      <ArchivePatientDialog
        patient={isConfirmingArchive ? patient : null}
        isSubmitting={isArchiving}
        error={archiveError}
        onCancel={closeArchiveDialog}
        onConfirm={handleConfirmArchive}
      />
    </div>
  )
}
