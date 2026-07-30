import { Link, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { Card } from '@/components/common/Card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { SummaryStat } from '@/components/common/SummaryStat'
import { PatientBreadcrumb } from '@/components/patients/PatientBreadcrumb'
import { AnalysisStatusBadge } from '@/components/analyses/AnalysisStatusBadge'
import { MedicationDiscrepancyCard } from '@/components/analyses/MedicationDiscrepancyCard'
import { usePatient } from '@/hooks/usePatient'
import { useAnalysisDetail } from '@/hooks/useAnalysisDetail'
import { discrepancySeverityLabel } from '@/utils/discrepancy'
import { patientAnalysesPath } from '@/routes/paths'
import type { DiscrepancySeverity, MedicationDiscrepancy } from '@/types/api'

function formatDateTime(value: string | null): string | null {
  if (!value) {
    return null
  }

  return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

// Ordering (and grouping) drives "most important findings first" - there is
// no "critical" tier to include here: DiscrepancySeverity only ever has
// high/medium/low (see docs/frontend.md for why a 4th tier was not invented
// just to match this issue's example wording).
const SEVERITY_GROUP_ORDER: DiscrepancySeverity[] = ['high', 'medium', 'low']

interface SeverityGroup {
  severity: DiscrepancySeverity
  items: MedicationDiscrepancy[]
}

function groupBySeverity(discrepancies: MedicationDiscrepancy[]): SeverityGroup[] {
  return SEVERITY_GROUP_ORDER.map((severity) => ({
    severity,
    items: discrepancies
      .filter((discrepancy) => discrepancy.severity === severity)
      .sort((a, b) => a.id - b.id),
  })).filter((group) => group.items.length > 0)
}

function countBySeverity(discrepancies: MedicationDiscrepancy[], severity: DiscrepancySeverity) {
  return discrepancies.filter((discrepancy) => discrepancy.severity === severity).length
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

  const discrepancies = analysis.medication_discrepancies
  const severityGroups = groupBySeverity(discrepancies)

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

      <section aria-labelledby="findings-heading" className="flex flex-col gap-4">
        <h2 id="findings-heading" className="text-lg font-semibold text-slate-900">
          Medication Reconciliation Findings
        </h2>

        <Card>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <SummaryStat label="Total" value={discrepancies.length} />
            <SummaryStat label="High" value={countBySeverity(discrepancies, 'high')} />
            <SummaryStat label="Medium" value={countBySeverity(discrepancies, 'medium')} />
            <SummaryStat label="Low" value={countBySeverity(discrepancies, 'low')} />
          </dl>
        </Card>

        {discrepancies.length === 0 ? (
          <Card role="status" className="flex flex-col items-center gap-2 py-10 text-center">
            <p className="text-sm font-semibold text-green-700">
              No medication inconsistencies were detected.
            </p>
            <p className="max-w-md text-sm text-slate-600">
              Reconciliation compared the medications extracted from this analysis's documents
              against {patient.first_name}'s medication list and found nothing to flag.
            </p>
          </Card>
        ) : (
          <div className="flex flex-col gap-6">
            {severityGroups.map((group) => (
              <div key={group.severity} className="flex flex-col gap-3">
                <h3 className="text-sm font-semibold text-slate-900">
                  {discrepancySeverityLabel(group.severity)} ({group.items.length})
                </h3>
                <ul className="flex flex-col gap-4">
                  {group.items.map((discrepancy) => (
                    <li key={discrepancy.id}>
                      <MedicationDiscrepancyCard discrepancy={discrepancy} />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
