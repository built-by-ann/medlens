import { Link, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { RecentAnalysesList } from '@/components/analyses/RecentAnalysesList'
import { AnalysesEmptyState } from '@/components/analyses/AnalysesEmptyState'
import { usePatient } from '@/hooks/usePatient'
import { usePatientAnalyses } from '@/hooks/usePatientAnalyses'
import { patientDetailPath, patientUploadPath } from '@/routes/paths'

export function PatientAnalysesPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)

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
  } = usePatientAnalyses(id)

  return (
    <div className="flex flex-col gap-8">
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
          <PageHeader
            title={`Analyses for ${patient.first_name} ${patient.last_name}`}
            description="Review past medication reconciliation analyses for this patient."
            actions={
              <Link
                to={patientUploadPath(patient.id)}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              >
                + Start analysis
              </Link>
            }
          />

          <Link
            to={patientDetailPath(patient.id)}
            className="self-start text-sm text-slate-600 hover:underline"
          >
            ← Back to {patient.first_name} {patient.last_name}
          </Link>

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
        </>
      )}
    </div>
  )
}
