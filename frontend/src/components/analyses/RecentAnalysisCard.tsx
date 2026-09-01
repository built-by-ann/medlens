import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Card } from '@/components/common/Card'
import { SummaryStat } from '@/components/common/SummaryStat'
import { FormError } from '@/components/common/FormError'
import { AnalysisStatusBadge } from '@/components/analyses/AnalysisStatusBadge'
import { AnalysisFailureNotice } from '@/components/analyses/AnalysisFailureNotice'
import { analysisStatusLabel } from '@/utils/analysisStatus'
import { analysisDetailPath } from '@/routes/paths'
import type { ApiError } from '@/api/client'
import type { AnalysisSummary } from '@/types/api'

function formatDateTime(value: string | null): string | null {
  if (!value) {
    return null
  }

  return new Date(value).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

interface RecentAnalysisCardProps {
  analysis: AnalysisSummary
  onDelete?: (id: number) => Promise<void>
  // Set only by the Dashboard's cross-patient Recent Analyses feed (Issue
  // #157); every other caller already has the patient established by the
  // page it's on, so this stays undefined (and unrendered) there.
  patientName?: string
}

export function RecentAnalysisCard({ analysis, onDelete, patientName }: RecentAnalysisCardProps) {
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const createdAt = formatDateTime(analysis.created_at)
  const completedAt = formatDateTime(analysis.completed_at)
  const statusLabel = analysisStatusLabel(analysis.status)

  async function handleDelete() {
    if (isDeleting || !onDelete) return

    setIsDeleting(true)
    setDeleteError(null)
    try {
      await onDelete(analysis.id)
    } catch (error) {
      setDeleteError((error as ApiError).message)
      setIsDeleting(false)
    }
  }

  return (
    <Card className="p-0">
      <Link
        to={analysisDetailPath(analysis.patient_id, analysis.id)}
        aria-label={
          patientName
            ? `View analysis for ${patientName} from ${createdAt ?? 'an unknown date'}, status: ${statusLabel}`
            : `View analysis from ${createdAt ?? 'an unknown date'}, status: ${statusLabel}`
        }
        className="flex flex-col gap-3 rounded-t-lg p-6 hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
      >
        {patientName && (
          <span className="text-sm font-semibold text-foreground">{patientName}</span>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2">
          <AnalysisStatusBadge status={analysis.status} />
          {createdAt && <span className="text-xs text-muted">{createdAt}</span>}
        </div>

        {analysis.summary && (
          <p className="line-clamp-2 text-sm text-foreground">{analysis.summary}</p>
        )}

        {analysis.status === 'failed' && analysis.error_message && (
          <AnalysisFailureNotice message={analysis.error_message} />
        )}

        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SummaryStat label="Documents" value={analysis.document_count} />
          <SummaryStat label="Findings" value={analysis.total_findings} />
          <SummaryStat label="Open" value={analysis.open_findings} />
          {completedAt && <SummaryStat label="Completed" value={completedAt} />}
        </dl>

        {analysis.provider && (
          <p className="text-xs text-muted">
            {analysis.provider}
            {analysis.model_name ? ` · ${analysis.model_name}` : ''}
          </p>
        )}
      </Link>

      {onDelete && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-6 py-3">
          {deleteError ? (
            <FormError message={deleteError} className="min-w-0 break-words" />
          ) : (
            <span />
          )}
          <button
            type="button"
            onClick={handleDelete}
            disabled={isDeleting}
            aria-label={`Delete analysis from ${createdAt ?? 'an unknown date'}`}
            className="shrink-0 cursor-pointer rounded-md px-2 py-1 text-xs font-medium text-danger hover:bg-danger/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isDeleting ? 'Removing...' : 'Delete'}
          </button>
        </div>
      )}
    </Card>
  )
}
