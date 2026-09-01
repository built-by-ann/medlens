import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { Card } from '@/components/common/Card'
import { PatientSearch } from '@/components/patients/PatientSearch'
import { PatientList } from '@/components/patients/PatientList'
import { EmptyPatientState } from '@/components/patients/EmptyPatientState'
import { ArchivePatientDialog } from '@/components/patients/ArchivePatientDialog'
import { filterPatients } from '@/components/patients/filterPatients'
import { sortPatientsByRecentActivity } from '@/components/patients/sortPatientsByRecentActivity'
import { StartAnalysisDialog } from '@/components/dashboard/StartAnalysisDialog'
import { RecentAnalysisCard } from '@/components/analyses/RecentAnalysisCard'
import { usePatients } from '@/hooks/usePatients'
import { useRecentAnalyses } from '@/hooks/useRecentAnalyses'
import { useAuth } from '@/hooks/useAuth'
import { ROUTES, createAnalysisPath } from '@/routes/paths'
import type { ApiError } from '@/api/client'
import type { Patient } from '@/types/api'

// A glance-and-go preview, not the full browsable list (that's
// PatientsPage); keeps the dashboard from growing unbounded as a provider
// accumulates patients over time.
const RECENT_PATIENTS_LIMIT = 3

// The same glance-and-go reasoning as RECENT_PATIENTS_LIMIT above, applied
// to the Recent Analyses feed (Issue #157).
const RECENT_ANALYSES_LIMIT = 3

// Issue #132 deliberately kept analysis creation off the Dashboard, since
// CreateAnalysisPage always needed a patient first and adding one here
// would have just duplicated the same "pick a patient" step every
// patient-scoped page already handles via its own URL. Issue #157 revisits
// that: the Dashboard is meant to be a real workflow starting point, so
// "New Analysis" now prompts for a patient (StartAnalysisDialog) and hands
// off to the exact same CreateAnalysisPage every other entry point already
// uses; nothing about analysis creation itself is duplicated here.
export function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { patients, isLoading, error, retry, archivePatient } = usePatients()
  const {
    analyses: recentAnalyses,
    isLoading: areAnalysesLoading,
    error: analysesError,
    retry: retryAnalyses,
  } = useRecentAnalyses(RECENT_ANALYSES_LIMIT)
  const [searchTerm, setSearchTerm] = useState('')
  const [patientPendingArchive, setPatientPendingArchive] = useState<Patient | null>(null)
  const [isArchiving, setIsArchiving] = useState(false)
  const [archiveError, setArchiveError] = useState<string | null>(null)
  const [isStartAnalysisOpen, setIsStartAnalysisOpen] = useState(false)

  const isSearching = searchTerm.trim().length > 0
  const canStartAnalysis = !isLoading && !error && patients.length > 0

  // Reuses the single list `usePatients()` already fetched; searching and
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

  function handleSelectPatientForAnalysis(patient: Patient) {
    setIsStartAnalysisOpen(false)
    navigate(createAnalysisPath(patient.id))
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title={user?.name ? `Welcome back, ${user.name}` : 'Welcome back'}
        description="Find a patient to continue their care, or start something new."
      />

      <nav aria-label="Quick actions" className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setIsStartAnalysisOpen(true)}
          disabled={!canStartAnalysis}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring disabled:cursor-not-allowed disabled:opacity-50"
        >
          + New Analysis
        </button>
        <Link
          to={ROUTES.newPatient}
          className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        >
          + New patient
        </Link>
        <Link
          to={ROUTES.patients}
          className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        >
          View all patients
        </Link>
      </nav>

      {/*
        Recent Patients and Recent Analyses sit side by side once there's
        room for two genuinely independent columns (lg: 1024px+); below
        that, tablet portrait and phone, they stack in the same order a
        screen reader already reads them in, so this is a purely visual
        rearrangement, not a second navigation path through the page.
      */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:items-start">
        <section aria-labelledby="patients-heading" className="flex flex-col gap-4">
          {/*
            Always rendered, even while loading/erroring/empty; matches
            Recent Analyses' heading below, which is never conditional
            either. Previously this heading only appeared once patients
            existed, so the empty state ("No patients yet") started flush
            with the top of the grid row while Recent Analyses' card sat
            below its own heading, so the two columns' cards ended up at
            different heights and looked misaligned. isSearching can only
            be true once PatientSearch is actually rendered (patients.length
            > 0, below), so this still reads "Recent patients" in every
            other case without needing its own branch.
          */}
          <h2 id="patients-heading" className="text-lg font-semibold text-foreground">
            {isSearching ? 'Search results' : 'Recent patients'}
          </h2>

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
            </>
          )}
        </section>

        <section aria-labelledby="recent-analyses-heading" className="flex flex-col gap-4">
          <h2 id="recent-analyses-heading" className="text-lg font-semibold text-foreground">
            Recent analyses
          </h2>

          {areAnalysesLoading && <LoadingSpinner label="Loading recent analyses" />}

          {!areAnalysesLoading && analysesError && (
            <ErrorState
              title="Couldn't load recent analyses"
              message={analysesError}
              onRetry={retryAnalyses}
            />
          )}

          {!areAnalysesLoading && !analysesError && recentAnalyses.length === 0 && (
            <Card className="flex flex-col items-center gap-3 py-10 text-center">
              <h3 className="text-sm font-semibold text-foreground">No analyses yet</h3>
              <p className="max-w-md text-sm text-muted">
                {canStartAnalysis
                  ? 'Start an analysis to compare medication information across a patient’s clinical documents.'
                  : 'Add your first patient, then start an analysis to compare medication information across their clinical documents.'}
              </p>
              <button
                type="button"
                onClick={() => setIsStartAnalysisOpen(true)}
                disabled={!canStartAnalysis}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring disabled:cursor-not-allowed disabled:opacity-50"
              >
                Start an analysis
              </button>
            </Card>
          )}

          {!areAnalysesLoading && !analysesError && recentAnalyses.length > 0 && (
            <ul className="flex flex-col gap-4">
              {recentAnalyses.map((analysis) => (
                <li key={analysis.id}>
                  <RecentAnalysisCard
                    analysis={analysis}
                    patientName={`${analysis.patient.first_name} ${analysis.patient.last_name}`}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <StartAnalysisDialog
        isOpen={isStartAnalysisOpen}
        patients={patients}
        onClose={() => setIsStartAnalysisOpen(false)}
        onSelectPatient={handleSelectPatientForAnalysis}
      />

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
