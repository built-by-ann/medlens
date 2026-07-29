import { Link, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { Card } from '@/components/common/Card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { SummaryStat } from '@/components/common/SummaryStat'
import { PatientBreadcrumb } from '@/components/patients/PatientBreadcrumb'
import { AnalysisStatusBadge } from '@/components/analyses/AnalysisStatusBadge'
import { usePatient } from '@/hooks/usePatient'
import { useAnalysisDetail } from '@/hooks/useAnalysisDetail'
import { patientAnalysesPath } from '@/routes/paths'

function formatDateTime(value: string | null): string | null {
  if (!value) {
    return null
  }

  return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function AnalysisDetailPage() {
  const { patientId, analysisId } = useParams<{ patientId: string; analysisId: string }>()
  const id = Number(patientId)
  const analysisIdNumber = Number(analysisId)

  const {
    patient,
    isLoading: isPatientLoading,
    error: patientError,
    retry: retryPatient,
  } = usePatient(id)
  const {
    analysis,
    isLoading: isAnalysisLoading,
    error: analysisError,
    retry: retryAnalysis,
  } = useAnalysisDetail(id, analysisIdNumber)

  if (isPatientLoading || isAnalysisLoading) {
    return <LoadingSpinner label="Loading analysis" />
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

  if (analysisError || !analysis) {
    return (
      <ErrorState
        title="Couldn't load this analysis"
        message={analysisError ?? 'Analysis not found.'}
        onRetry={retryAnalysis}
      />
    )
  }

  const createdAt = formatDateTime(analysis.created_at)
  const startedAt = formatDateTime(analysis.started_at)
  const completedAt = formatDateTime(analysis.completed_at)

  return (
    <div className="flex flex-col gap-6">
      <PatientBreadcrumb
        patient={patient}
        trail={[
          { label: 'Analyses', to: patientAnalysesPath(patient.id) },
          { label: `Analysis #${analysis.id}` },
        ]}
      />

      <PageHeader
        title={`Analysis #${analysis.id}`}
        description={`For ${patient.first_name} ${patient.last_name}`}
        actions={<AnalysisStatusBadge status={analysis.status} />}
      />

      <Link
        to={patientAnalysesPath(patient.id)}
        className="self-start text-sm text-slate-600 hover:underline"
      >
        ← Back to analyses
      </Link>

      <Card className="flex flex-col gap-4">
        {analysis.status === 'failed' && analysis.error_message && (
          <p role="alert" className="text-sm text-red-600">
            {analysis.error_message}
          </p>
        )}

        {analysis.summary && <p className="text-sm text-slate-700">{analysis.summary}</p>}

        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {createdAt && <SummaryStat label="Created" value={createdAt} />}
          {startedAt && <SummaryStat label="Started" value={startedAt} />}
          {completedAt && <SummaryStat label="Completed" value={completedAt} />}
          {analysis.provider && <SummaryStat label="Provider" value={analysis.provider} />}
          {analysis.model_name && <SummaryStat label="Model" value={analysis.model_name} />}
        </dl>
      </Card>

      <Card>
        <p className="text-sm text-slate-600">
          Detailed medication findings and inconsistency detection will be added in a future issue.
        </p>
      </Card>
    </div>
  )
}
