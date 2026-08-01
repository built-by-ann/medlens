import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { PatientSearch } from '@/components/patients/PatientSearch'
import { PatientList } from '@/components/patients/PatientList'
import { EmptyPatientState } from '@/components/patients/EmptyPatientState'
import { ArchivePatientDialog } from '@/components/patients/ArchivePatientDialog'
import { filterPatients } from '@/components/patients/filterPatients'
import { usePatients } from '@/hooks/usePatients'
import { ROUTES } from '@/routes/paths'
import type { ApiError } from '@/api/client'
import type { Patient } from '@/types/api'

export function PatientsPage() {
  const { patients, isLoading, error, retry, archivePatient } = usePatients()
  const [searchTerm, setSearchTerm] = useState('')
  const [patientPendingArchive, setPatientPendingArchive] = useState<Patient | null>(null)
  const [isArchiving, setIsArchiving] = useState(false)
  const [archiveError, setArchiveError] = useState<string | null>(null)

  const filteredPatients = useMemo(
    () => filterPatients(patients, searchTerm),
    [patients, searchTerm],
  )

  function closeArchiveDialog() {
    if (isArchiving) return
    setPatientPendingArchive(null)
    setArchiveError(null)
  }

  async function handleConfirmArchive() {
    if (!patientPendingArchive || isArchiving) return

    setIsArchiving(true)
    setArchiveError(null)
    try {
      await archivePatient(patientPendingArchive.id)
      setPatientPendingArchive(null)
    } catch (caughtError) {
      setArchiveError((caughtError as ApiError).message)
    } finally {
      setIsArchiving(false)
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Patients"
        description="Search your active patients or add a new one."
        actions={
          <Link
            to={ROUTES.newPatient}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
          >
            + New patient
          </Link>
        }
      />

      {!isLoading && !error && patients.length > 0 && (
        <PatientSearch value={searchTerm} onChange={setSearchTerm} />
      )}

      {isLoading && <LoadingSpinner label="Loading your patients" />}

      {!isLoading && error && (
        <ErrorState title="Couldn't load your patients" message={error} onRetry={retry} />
      )}

      {!isLoading && !error && filteredPatients.length === 0 && (
        <EmptyPatientState hasActivePatients={patients.length > 0} />
      )}

      {!isLoading && !error && filteredPatients.length > 0 && (
        <PatientList patients={filteredPatients} onArchiveRequest={setPatientPendingArchive} />
      )}

      <ArchivePatientDialog
        patient={patientPendingArchive}
        isSubmitting={isArchiving}
        error={archiveError}
        onCancel={closeArchiveDialog}
        onConfirm={handleConfirmArchive}
      />
    </div>
  )
}
