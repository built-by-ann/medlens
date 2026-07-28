import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { PatientDetails } from '@/components/patients/PatientDetails'
import { ArchivePatientDialog } from '@/components/patients/ArchivePatientDialog'
import { usePatient } from '@/hooks/usePatient'
import { archivePatient } from '@/api/patients'
import { ROUTES, patientEditPath } from '@/routes/paths'
import type { ApiError } from '@/api/client'

export function PatientOverviewPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const navigate = useNavigate()
  const id = Number(patientId)
  const { patient, isLoading, error, retry } = usePatient(id)

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
          <PageHeader
            title={`${patient.first_name} ${patient.last_name}`}
            description="Patient overview"
            actions={
              <div className="flex gap-2">
                <Link
                  to={patientEditPath(patient.id)}
                  className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                >
                  Edit
                </Link>
                <button
                  type="button"
                  onClick={() => setIsConfirmingArchive(true)}
                  className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                >
                  Archive
                </button>
              </div>
            }
          />

          <PatientDetails patient={patient} />

          <p className="text-sm text-slate-500">
            Medications, clinical documents, and analysis history will appear here in a future
            update.
          </p>
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
