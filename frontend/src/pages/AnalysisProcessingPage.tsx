import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { Card } from '@/components/common/Card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { SummaryStat } from '@/components/common/SummaryStat'
import { PatientBreadcrumb } from '@/components/patients/PatientBreadcrumb'
import { AnalysisStatusBadge } from '@/components/analyses/AnalysisStatusBadge'
import { usePatient } from '@/hooks/usePatient'
import { useCreateAnalysis, type SubmitInput } from '@/hooks/useCreateAnalysis'
import { useAnalysisPolling } from '@/hooks/useAnalysisPolling'
import { useRotatingMessages } from '@/hooks/useRotatingMessages'
import {
  analysisDetailPath,
  patientAnalysesPath,
  patientDetailPath,
  patientUploadPath,
} from '@/routes/paths'

const PROGRESS_MESSAGES = [
  'Preparing analysis...',
  'Extracting medication mentions...',
  'Reconciling medication list...',
  'Comparing documentation...',
  'Generating clinical summary...',
  'Finalizing analysis...',
] as const

function formatDateTime(value: string | null): string | null {
  if (!value) return null
  return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

interface FailureCardProps {
  message: string
  onRetry?: () => void
  patientId: number
}

function FailureCard({ message, onRetry, patientId }: FailureCardProps) {
  return (
    <Card role="alert" className="flex flex-col items-center gap-4 py-12 text-center">
      <h2 className="text-lg font-semibold text-slate-900">Analysis failed</h2>
      <p className="max-w-md text-sm text-slate-600">{message}</p>
      <div className="flex flex-wrap justify-center gap-2">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="cursor-pointer rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            Try again
          </button>
        )}
        <Link
          to={patientDetailPath(patientId)}
          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Return to Patient Overview
        </Link>
        <Link
          to={patientAnalysesPath(patientId)}
          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Return to Analysis History
        </Link>
      </div>
    </Card>
  )
}

export function AnalysisProcessingPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)
  const location = useLocation()
  const navigate = useNavigate()

  const {
    patient,
    isLoading: isPatientLoading,
    error: patientError,
    retry: retryPatient,
  } = usePatient(id)
  const { isSubmitting, error: submitError, submit } = useCreateAnalysis(id)
  const [analysisId, setAnalysisId] = useState<number | null>(null)
  const message = useRotatingMessages(PROGRESS_MESSAGES, 3500)

  const submission = (location.state as SubmitInput | null) ?? null
  const { analysis, error: pollError } = useAnalysisPolling(id, analysisId)

  const runSubmission = useCallback(async () => {
    if (!submission) return

    try {
      const newAnalysisId = await submit(submission)
      setAnalysisId(newAnalysisId)
    } catch {
      // submitError already reflects this via the hook's own state.
    }
  }, [submission, submit])

  useEffect(() => {
    // Intentionally run once on mount only - retries are user-triggered.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void runSubmission()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (analysis?.status === 'completed') {
      navigate(analysisDetailPath(id, analysis.id), { replace: true })
    }
  }, [analysis, id, navigate])

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

  if (!submission) {
    return (
      <div className="flex flex-col gap-8">
        <PatientBreadcrumb patient={patient} trail={[{ label: 'Processing' }]} />
        <PageHeader
          title="Nothing to process"
          description={`For ${patient.first_name} ${patient.last_name}`}
        />
        <Card className="flex flex-col items-center gap-4 py-12 text-center">
          <p className="max-w-md text-sm text-slate-600">
            This page only works right after starting an analysis, either by uploading documents or
            selecting existing ones.
          </p>
          <Link
            to={patientUploadPath(patient.id)}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            Go to Upload
          </Link>
        </Card>
      </div>
    )
  }

  const createdAt = formatDateTime(analysis?.created_at ?? null)

  const failureMessage = submitError
    ? submitError
    : analysis?.status === 'failed'
      ? (analysis.error_message ?? 'The analysis failed to complete.')
      : pollError
        ? "We couldn't confirm the status of this analysis. It may still complete - check Analysis History for updates."
        : null

  const isFailed = !isSubmitting && failureMessage !== null

  return (
    <div className="flex flex-col gap-8">
      <PatientBreadcrumb patient={patient} trail={[{ label: 'Processing' }]} />

      <PageHeader
        title="Analysis Processing"
        description={`For ${patient.first_name} ${patient.last_name}`}
      />

      {isFailed ? (
        <FailureCard
          message={failureMessage}
          onRetry={
            submitError || analysis?.status === 'failed' ? () => void runSubmission() : undefined
          }
          patientId={patient.id}
        />
      ) : (
        <Card aria-live="polite" className="flex flex-col items-center gap-3 py-12 text-center">
          <LoadingSpinner label="Analysis in progress" />
          <p className="text-base font-semibold text-slate-900">{message}</p>
          <p className="text-sm text-slate-600">AI is reviewing uploaded clinical documents.</p>
          <p className="text-sm text-slate-600">Estimated time: 10-30 seconds</p>
          <p className="text-sm font-medium text-slate-700">Please keep this page open.</p>

          {analysis && (
            <dl className="mt-4 grid grid-cols-2 gap-4">
              {createdAt && <SummaryStat label="Created" value={createdAt} />}
              <div className="flex flex-col gap-0.5">
                <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">
                  Status
                </dt>
                <dd>
                  <AnalysisStatusBadge status={analysis.status} />
                </dd>
              </div>
            </dl>
          )}
        </Card>
      )}
    </div>
  )
}
