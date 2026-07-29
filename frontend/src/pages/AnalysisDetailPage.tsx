import { Link, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { Card } from '@/components/common/Card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { SummaryStat } from '@/components/common/SummaryStat'
import { PatientBreadcrumb } from '@/components/patients/PatientBreadcrumb'
import { PatientDetails } from '@/components/patients/PatientDetails'
import { AnalysisStatusBadge } from '@/components/analyses/AnalysisStatusBadge'
import { MedicationDiscrepancyCard } from '@/components/analyses/MedicationDiscrepancyCard'
import { usePatient } from '@/hooks/usePatient'
import { useAnalysisDetail } from '@/hooks/useAnalysisDetail'
import { DISCREPANCY_SEVERITY_RANK } from '@/utils/discrepancy'
import { patientAnalysesPath, patientDetailPath } from '@/routes/paths'
import type { MedicationDiscrepancy } from '@/types/api'

function formatDateTime(value: string | null): string | null {
  if (!value) {
    return null
  }

  return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function formatDuration(startedAt: string | null, completedAt: string | null): string | null {
  if (!startedAt || !completedAt) {
    return null
  }

  const milliseconds = new Date(completedAt).getTime() - new Date(startedAt).getTime()

  if (!Number.isFinite(milliseconds) || milliseconds < 0) {
    return null
  }

  const totalSeconds = Math.round(milliseconds / 1000)

  if (totalSeconds < 60) {
    return `${totalSeconds}s`
  }

  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60

  return `${minutes}m ${seconds}s`
}

function sortFindings(findings: MedicationDiscrepancy[]): MedicationDiscrepancy[] {
  return [...findings].sort((a, b) => {
    const severityDiff =
      DISCREPANCY_SEVERITY_RANK[a.severity] - DISCREPANCY_SEVERITY_RANK[b.severity]

    return severityDiff !== 0 ? severityDiff : a.id - b.id
  })
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
  const completedAt = formatDateTime(analysis.completed_at)
  const duration = formatDuration(analysis.started_at, analysis.completed_at)
  const findings = sortFindings(analysis.medication_discrepancies)

  return (
    <div className="flex flex-col gap-8">
      <PatientBreadcrumb
        patient={patient}
        trail={[
          { label: 'Analyses', to: patientAnalysesPath(patient.id) },
          { label: `Analysis #${analysis.id}` },
        ]}
      />

      <PageHeader
        title="Analysis Results"
        description={`Analysis #${analysis.id} for ${patient.first_name} ${patient.last_name}`}
        actions={<AnalysisStatusBadge status={analysis.status} />}
      />

      <nav aria-label="Analysis navigation" className="flex flex-wrap gap-4 text-sm">
        <Link
          to={patientDetailPath(patient.id)}
          className="text-slate-600 hover:text-slate-900 hover:underline"
        >
          ← Patient Overview
        </Link>
        <Link
          to={patientAnalysesPath(patient.id)}
          className="text-slate-600 hover:text-slate-900 hover:underline"
        >
          Analysis History
        </Link>
        <Link
          to={`${patientDetailPath(patient.id)}#documents-heading`}
          className="text-slate-600 hover:text-slate-900 hover:underline"
        >
          Clinical Documents
        </Link>
      </nav>

      {analysis.status === 'failed' && analysis.error_message && (
        <p role="alert" className="text-sm text-red-600">
          {analysis.error_message}
        </p>
      )}

      <section aria-labelledby="patient-info-heading" className="flex flex-col gap-4">
        <h2 id="patient-info-heading" className="text-lg font-semibold text-slate-900">
          Patient Information
        </h2>
        <PatientDetails patient={patient} />
      </section>

      <section aria-labelledby="summary-heading" className="flex flex-col gap-4">
        <h2 id="summary-heading" className="text-lg font-semibold text-slate-900">
          Analysis Summary
        </h2>
        <Card className="flex flex-col gap-4">
          {analysis.summary ? (
            <p className="text-sm text-slate-700">{analysis.summary}</p>
          ) : (
            <p className="text-sm text-slate-500">No AI summary was generated for this analysis.</p>
          )}
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <SummaryStat label="Discrepancies found" value={findings.length} />
            <SummaryStat label="Medications analyzed" value={analysis.medication_mentions.length} />
            <SummaryStat label="Documents analyzed" value={analysis.document_count} />
          </dl>
        </Card>
      </section>

      <section aria-labelledby="findings-heading" className="flex flex-col gap-4">
        <h2 id="findings-heading" className="text-lg font-semibold text-slate-900">
          Medication Reconciliation Findings
        </h2>
        {findings.length > 0 ? (
          <ul className="flex flex-col gap-4">
            {findings.map((finding) => (
              <li key={finding.id}>
                <MedicationDiscrepancyCard discrepancy={finding} />
              </li>
            ))}
          </ul>
        ) : (
          <Card>
            <p className="text-sm text-slate-600">
              No medication reconciliation findings are available for this analysis.
            </p>
          </Card>
        )}
      </section>

      <section aria-labelledby="metadata-heading" className="flex flex-col gap-4">
        <h2 id="metadata-heading" className="text-lg font-semibold text-slate-900">
          Analysis Metadata
        </h2>
        <Card>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <SummaryStat label="Analysis ID" value={analysis.id} />
            {createdAt && <SummaryStat label="Created" value={createdAt} />}
            {completedAt && <SummaryStat label="Completed" value={completedAt} />}
            {analysis.provider && <SummaryStat label="Provider" value={analysis.provider} />}
            {analysis.model_name && <SummaryStat label="Model" value={analysis.model_name} />}
            {duration && <SummaryStat label="Processing duration" value={duration} />}
          </dl>
        </Card>
      </section>
    </div>
  )
}
