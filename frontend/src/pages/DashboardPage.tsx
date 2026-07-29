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
import { sortPatientsByRecentActivity } from '@/components/patients/sortPatientsByRecentActivity'
import { usePatients } from '@/hooks/usePatients'
import { useAuth } from '@/hooks/useAuth'
import { ROUTES } from '@/routes/paths'
import type { ApiError } from '@/api/client'
import type { Patient } from '@/types/api'

// A glance-and-go preview, not the full browsable list (that's
// PatientsPage) - keeps the dashboard from growing unbounded as a provider
// accumulates patients over time.
const RECENT_PATIENTS_LIMIT = 5

// As of Sprint 3.5 (Issue #132), the Dashboard answers "what patient do I
// want to work on?" instead of "what analysis recently happened?" -
// analyses, documents, and medications remain fully managed from within a
// patient's own pages (see PatientOverviewPage); nothing here duplicates
// that workflow.
export function DashboardPage() {
  const { user } = useAuth()
  const { patients, isLoading, error, retry, archivePatient } = usePatients()
  const [searchTerm, setSearchTerm] = useState('')
  const [patientPendingArchive, setPatientPendingArchive] = useState<Patient | null>(null)
  const [isArchiving, setIsArchiving] = useState(false)
  const [archiveError, setArchiveError] = useState<string | null>(null)

  const isSearching = searchTerm.trim().length > 0

  // Reuses the single list `usePatients()` already fetched - searching and
  // "recent patients" are two different views over the same data, never two
  // separate requests.
  const recentPatients = useMemo(
    () => sortPatientsByRecentActivity(patients, RECENT_PATIENTS_LIMIT),
    [patients],
  )
  const searchResults = useMemo(() => filterPatients(patients, searchTerm), [patients, searchTerm])
  const visiblePatients = isSearching ? searchResults : recentPatients

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
        title={user?.name ? `Welcome back, ${user.name}` : 'Welcome back'}
        description="Find a patient to continue their care, or add a new one."
      />

      {isLoading && <LoadingSpinner label="Loading your patients" />}

      {!isLoading && error && (
        <ErrorState title="Couldn't load your patients" message={error} onRetry={retry} />
      )}

      {!isLoading && !error && patients.length === 0 && (
        <EmptyPatientState hasActivePatients={false} />
      )}

      {!isLoading && !error && patients.length > 0 && (
        <>
          <PatientSearch value={searchTerm} onChange={setSearchTerm} />

          <section aria-labelledby="patients-heading" className="flex flex-col gap-4">
            <h2 id="patients-heading" className="text-lg font-semibold text-slate-900">
              {isSearching ? 'Search results' : 'Recent patients'}
            </h2>

            {visiblePatients.length === 0 ? (
              <EmptyPatientState hasActivePatients={true} />
            ) : (
              <PatientList
                patients={visiblePatients}
                onArchiveRequest={setPatientPendingArchive}
                showStatus
                showUpdatedAt
              />
            )}
          </section>

          <nav aria-label="Quick actions" className="flex flex-wrap gap-2">
            <Link
              to={ROUTES.newPatient}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            >
              + New patient
            </Link>
            <Link
              to={ROUTES.patients}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            >
              View all patients
            </Link>
          </nav>
        </>
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
