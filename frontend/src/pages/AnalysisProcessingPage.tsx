import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { Card } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
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
      <h2 className="text-lg font-semibold text-foreground">Analysis failed</h2>
      <p className="max-w-md text-sm text-muted">{message}</p>
      <div className="flex flex-wrap justify-center gap-2">
        {onRetry && (
          <Button
            onClick={onRetry}
            className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
          >
            Try again
          </Button>
        )}
        <Link
          to={patientDetailPath(patientId)}
          className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        >
          Return to Patient Overview
        </Link>
        <Link
          to={patientAnalysesPath(patientId)}
          className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
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
  const { isSubmitting, error: submitError, failedItemLabel, submit } = useCreateAnalysis(id)
  const [analysisId, setAnalysisId] = useState<number | null>(null)
  const message = useRotatingMessages(PROGRESS_MESSAGES, 3500)

  const submission = (location.state as SubmitInput | null) ?? null
  const { analysis, error: pollError, retry: retryPolling } = useAnalysisPolling(id, analysisId)

  const runSubmission = useCallback(async () => {
    if (!submission) return

    try {
      const newAnalysisId = await submit(submission)
      setAnalysisId(newAnalysisId)
    } catch {
      // submitError already reflects this via the hook's own state.
    }
  }, [submission, submit])

  // Guards the automatic mount-time submission below against firing more
  // than once per mount - most notably React Strict Mode's dev-only
  // double-invoke of mount effects, which (unlike a merely wasted re-fetch)
  // would otherwise re-run the real upload-and-create-analysis sequence a
  // second time, producing a duplicate ClinicalDocument and a duplicate
  // Analysis. Deliberately not reset on retry: the "Try again" button calls
  // runSubmission() directly, bypassing this effect entirely.
  const hasStartedSubmissionRef = useRef(false)

  useEffect(() => {
    if (hasStartedSubmissionRef.current) return
    hasStartedSubmissionRef.current = true

    // Intentionally run once on mount only - retries are user-triggered.
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
          <p className="max-w-md text-sm text-muted">
            This page only works right after starting an analysis, either by uploading documents or
            selecting existing ones.
          </p>
          <Link
            to={patientUploadPath(patient.id)}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
          >
            Go to Upload
          </Link>
        </Card>
      </div>
    )
  }

  const createdAt = formatDateTime(analysis?.created_at ?? null)

  // Names which file/note failed to upload, when known, so a submission
  // that combined several documents doesn't leave the user guessing which
  // one needs fixing.
  const failureMessage = submitError
    ? failedItemLabel
      ? `${failedItemLabel}: ${submitError}`
      : submitError
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
            submitError || analysis?.status === 'failed'
              ? () => void runSubmission()
              : pollError
                ? retryPolling
                : undefined
          }
          patientId={patient.id}
        />
      ) : (
        <Card aria-live="polite" className="flex flex-col items-center gap-3 py-12 text-center">
          <LoadingSpinner label="Analysis in progress" />
          <p className="text-base font-semibold text-foreground">{message}</p>
          <p className="text-sm text-muted">AI is reviewing uploaded clinical documents.</p>
          <p className="text-sm text-muted">Estimated time: 10-30 seconds</p>
          <p className="text-sm font-medium text-foreground">Please keep this page open.</p>

          {analysis && (
            <dl className="mt-4 grid grid-cols-2 gap-4">
              {createdAt && <SummaryStat label="Created" value={createdAt} />}
              <div className="flex flex-col gap-0.5">
                <dt className="text-xs font-medium tracking-wide text-muted uppercase">Status</dt>
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
