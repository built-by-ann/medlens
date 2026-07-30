import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { Card } from '@/components/common/Card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { SummaryStat } from '@/components/common/SummaryStat'
import { PatientPageNav } from '@/components/patients/PatientPageNav'
import { AnalysisStatusBadge } from '@/components/analyses/AnalysisStatusBadge'
import { MedicationDiscrepancyCard } from '@/components/analyses/MedicationDiscrepancyCard'
import { DeleteAnalysisDialog } from '@/components/analyses/DeleteAnalysisDialog'
import { usePatient } from '@/hooks/usePatient'
import { useAnalysisDetail } from '@/hooks/useAnalysisDetail'
import { discrepancySeverityLabel } from '@/utils/discrepancy'
import { patientAnalysesPath } from '@/routes/paths'
import { cn } from '@/utils/cn'
import { deleteAnalysis } from '@/api/analyses'
import type { ApiError } from '@/api/client'
import type {
  AnalysisInconsistency,
  AnalysisMedicationMention,
  DiscrepancySeverity,
  MedicationDiscrepancy,
} from '@/types/api'

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

function AiGeneratedBadge() {
  return (
    <span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-700">
      AI-generated
    </span>
  )
}

function DeterministicBadge() {
  return (
    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
      Deterministic
    </span>
  )
}

function MedicationMentionItem({ mention }: { mention: AnalysisMedicationMention }) {
  const details = [mention.dosage, mention.route, mention.frequency, mention.status]
    .filter(Boolean)
    .join(' · ')

  return (
    <li className="rounded-md bg-violet-50 p-3">
      <p className="text-sm font-medium text-slate-900">{mention.medication_name}</p>
      {details && <p className="text-xs text-slate-600">{details}</p>}
      {mention.notes && <p className="mt-1 text-sm text-slate-700">{mention.notes}</p>}
    </li>
  )
}

// Local-only: whether a follow-up question has been reviewed is not persisted
// anywhere in the backend, so this checklist's checked state resets on reload.
function FollowUpQuestionsChecklist({ items }: { items: AnalysisInconsistency[] }) {
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set())

  function toggle(id: number) {
    setCheckedIds((previous) => {
      const next = new Set(previous)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  return (
    <ul className="flex flex-col gap-2">
      {items.map((item) => {
        const checked = checkedIds.has(item.id)
        const inputId = `follow-up-question-${item.id}`

        return (
          <li key={item.id} className="flex items-start gap-2">
            <input
              id={inputId}
              type="checkbox"
              checked={checked}
              onChange={() => toggle(item.id)}
              className="mt-0.5 h-4 w-4 rounded border-slate-300 text-violet-600 focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-1"
            />
            <label
              htmlFor={inputId}
              className={cn('text-sm text-slate-700', checked && 'text-slate-400 line-through')}
            >
              {item.description}
            </label>
          </li>
        )
      })}
    </ul>
  )
}

export function AnalysisDetailPage() {
  const { patientId, analysisId } = useParams<{ patientId: string; analysisId: string }>()
  const id = Number(patientId)
  const analysisIdNumber = Number(analysisId)
  const navigate = useNavigate()

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

  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

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
  const medicationMentions = analysis.medication_mentions
  const followUpQuestions = analysis.possible_inconsistencies
  const patientName = `${patient.first_name} ${patient.last_name}`

  function openDeleteDialog() {
    setDeleteError(null)
    setIsDeleteDialogOpen(true)
  }

  function closeDeleteDialog() {
    if (isDeleting) return
    setIsDeleteDialogOpen(false)
    setDeleteError(null)
  }

  async function handleConfirmDelete() {
    if (isDeleting || !analysis) return

    setIsDeleting(true)
    setDeleteError(null)
    try {
      // `id`, not `patient.id`: they're the same patient once loaded, but
      // `id` (from useParams, a plain number) needs no null-narrowing of
      // `patient` inside this closure.
      await deleteAnalysis(id, analysis.id)
      navigate(patientAnalysesPath(id), {
        state: { flashMessage: `Analysis #${analysis.id} was deleted.` },
      })
    } catch (caughtError) {
      setDeleteError((caughtError as ApiError).message)
      setIsDeleting(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PatientPageNav
        patient={patient}
        trail={[
          { label: 'Analyses', to: patientAnalysesPath(patient.id) },
          { label: `Analysis #${analysis.id}` },
        ]}
        backTo={patientAnalysesPath(patient.id)}
        backLabel="analyses"
      />

      <PageHeader
        title={`Analysis #${analysis.id}`}
        description={`For ${patient.first_name} ${patient.last_name}`}
        actions={
          <>
            <AnalysisStatusBadge status={analysis.status} />
            <button
              type="button"
              onClick={openDeleteDialog}
              className="rounded-md px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            >
              Delete analysis
            </button>
          </>
        }
      />

      {analysis.status === 'failed' && analysis.error_message && (
        <Card role="alert" className="border-l-4 border-l-red-500">
          <p className="text-sm text-red-600">{analysis.error_message}</p>
        </Card>
      )}

      {/*
        AI-generated content (summary, medications mentioned, follow-up
        questions) gets its own violet-accented section, visually distinct
        from the deterministic reconciliation findings below - the badges
        and left border repeat that distinction so it never rests on color
        alone. There is no "Key clinical observations" or "Mentioned
        conditions" section here: the AI response schema (app/ai/schemas.py)
        has no such structured fields, only summary/medication_mentions/
        possible_inconsistencies, so nothing is fabricated to fill them in
        (see docs/frontend.md).
      */}
      <section aria-labelledby="ai-summary-heading" className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="ai-summary-heading" className="text-lg font-semibold text-slate-900">
            AI Summary
          </h2>
          <AiGeneratedBadge />
        </div>

        <Card className="flex flex-col gap-4 border-l-4 border-l-violet-400">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Summary</h3>
            {analysis.summary ? (
              <p className="mt-1 text-sm text-slate-700">{analysis.summary}</p>
            ) : (
              <p className="mt-1 text-sm text-slate-500">
                No AI summary is available for this analysis.
              </p>
            )}
          </div>

          {medicationMentions.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Medications Mentioned</h3>
              <ul className="mt-2 flex flex-col gap-2">
                {medicationMentions.map((mention) => (
                  <MedicationMentionItem key={mention.id} mention={mention} />
                ))}
              </ul>
            </div>
          )}

          {followUpQuestions.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Follow-up Questions</h3>
              <div className="mt-2">
                <FollowUpQuestionsChecklist items={followUpQuestions} />
              </div>
            </div>
          )}

          <div className="border-t border-slate-200 pt-4">
            <h3 className="text-xs font-medium tracking-wide text-slate-500 uppercase">
              Summary Metadata
            </h3>
            <dl className="mt-2 grid grid-cols-2 gap-4 sm:grid-cols-3">
              {createdAt && <SummaryStat label="Created" value={createdAt} />}
              {startedAt && <SummaryStat label="Started" value={startedAt} />}
              {completedAt && <SummaryStat label="Completed" value={completedAt} />}
              {analysis.provider && <SummaryStat label="Provider" value={analysis.provider} />}
              {analysis.model_name && <SummaryStat label="Model" value={analysis.model_name} />}
              <SummaryStat label="Documents analyzed" value={analysis.document_count} />
            </dl>
          </div>
        </Card>
      </section>

      <section aria-labelledby="findings-heading" className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="findings-heading" className="text-lg font-semibold text-slate-900">
            Medication Reconciliation Findings
          </h2>
          <DeterministicBadge />
        </div>

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

      <DeleteAnalysisDialog
        target={isDeleteDialogOpen ? { id: analysis.id, patientName } : null}
        isSubmitting={isDeleting}
        error={deleteError}
        onCancel={closeDeleteDialog}
        onConfirm={handleConfirmDelete}
      />
    </div>
  )
}
