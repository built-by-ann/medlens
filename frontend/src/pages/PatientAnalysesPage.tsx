import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { PatientPageNav } from '@/components/patients/PatientPageNav'
import { RecentAnalysesList } from '@/components/analyses/RecentAnalysesList'
import { AnalysesEmptyState } from '@/components/analyses/AnalysesEmptyState'
import { usePatient } from '@/hooks/usePatient'
import { usePatientAnalyses } from '@/hooks/usePatientAnalyses'
import { createAnalysisPath, patientDetailPath } from '@/routes/paths'

// Set by AnalysisDetailPage after a successful delete (see DeleteAnalysisDialog),
// via navigate(patientAnalysesPath(id), { state: { flashMessage } }).
interface AnalysesPageLocationState {
  flashMessage?: string
}

const FLASH_MESSAGE_DURATION_MS = 6000

export function PatientAnalysesPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)
  const location = useLocation()
  const navigate = useNavigate()

  const [flashMessage, setFlashMessage] = useState<string | null>(null)

  useEffect(() => {
    const state = location.state as AnalysesPageLocationState | null
    if (!state?.flashMessage) return

    // Syncing from the router's own external state (location.state), the
    // same justification useAnalysisDetail's loading-reset effect uses.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFlashMessage(state.flashMessage)
    // Clear the router state so refreshing or navigating back to this entry
    // doesn't redisplay a notification for an action that already happened.
    navigate(location.pathname, { replace: true, state: null })
  }, [location.state, location.pathname, navigate])

  useEffect(() => {
    if (!flashMessage) return

    const timer = setTimeout(() => setFlashMessage(null), FLASH_MESSAGE_DURATION_MS)
    return () => clearTimeout(timer)
  }, [flashMessage])

  const {
    patient,
    isLoading: isPatientLoading,
    error: patientError,
    retry: retryPatient,
  } = usePatient(id)
  const {
    analyses,
    isLoading: areAnalysesLoading,
    error: analysesError,
    retry: retryAnalyses,
    removeAnalysis,
  } = usePatientAnalyses(id, 50)

  return (
    <div className="flex flex-col gap-8">
      {flashMessage && (
        <div
          role="status"
          className="flex items-center justify-between gap-3 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800"
        >
          <span>{flashMessage}</span>
          <button
            type="button"
            onClick={() => setFlashMessage(null)}
            aria-label="Dismiss notification"
            className="rounded-md px-1 text-green-700 hover:text-green-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            ✕
          </button>
        </div>
      )}

      {isPatientLoading && <LoadingSpinner label="Loading patient" />}

      {!isPatientLoading && patientError && (
        <ErrorState
          title="Couldn't load this patient"
          message={patientError}
          onRetry={retryPatient}
        />
      )}

      {!isPatientLoading && !patientError && patient && (
        <>
          <PatientPageNav
            patient={patient}
            trail={[{ label: 'Analyses' }]}
            backTo={patientDetailPath(patient.id)}
            backLabel={`${patient.first_name} ${patient.last_name}`}
          />

          <PageHeader
            title={`Analyses for ${patient.first_name} ${patient.last_name}`}
            description="Review past medication reconciliation analyses for this patient."
            actions={
              <Link
                to={createAnalysisPath(patient.id)}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              >
                + Start analysis
              </Link>
            }
          />

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
            <RecentAnalysesList analyses={analyses} onDelete={removeAnalysis} />
          )}
        </>
      )}
    </div>
  )
}
