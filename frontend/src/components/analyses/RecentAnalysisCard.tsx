import { Link } from 'react-router-dom'
import { Card } from '@/components/common/Card'
import { SummaryStat } from '@/components/common/SummaryStat'
import { analysisDetailPath } from '@/routes/paths'
import { cn } from '@/utils/cn'
import type { AnalysisSummary } from '@/types/api'

const STATUS_LABELS: Record<AnalysisSummary['status'], string> = {
  pending: 'Pending',
  processing: 'Processing',
  completed: 'Completed',
  failed: 'Failed',
}

// Status is always communicated via this visible text label, never by
// badge color alone.
const STATUS_BADGE_STYLES: Record<AnalysisSummary['status'], string> = {
  pending: 'bg-slate-100 text-slate-700',
  processing: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}

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
}

export function RecentAnalysisCard({ analysis }: RecentAnalysisCardProps) {
  const createdAt = formatDateTime(analysis.created_at)
  const completedAt = formatDateTime(analysis.completed_at)
  const statusLabel = STATUS_LABELS[analysis.status]

  return (
    <Card className="p-0">
      <Link
        to={analysisDetailPath(analysis.patient_id, analysis.id)}
        aria-label={`View analysis from ${createdAt ?? 'an unknown date'}, status: ${statusLabel}`}
        className="flex flex-col gap-3 rounded-lg p-6 hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-xs font-medium',
              STATUS_BADGE_STYLES[analysis.status],
            )}
          >
            {statusLabel}
          </span>
          {createdAt && <span className="text-xs text-slate-500">{createdAt}</span>}
        </div>

        {analysis.summary && (
          <p className="line-clamp-2 text-sm text-slate-700">{analysis.summary}</p>
        )}

        {analysis.status === 'failed' && analysis.error_message && (
          <p className="text-sm text-red-600">{analysis.error_message}</p>
        )}

        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SummaryStat label="Documents" value={analysis.document_count} />
          <SummaryStat label="Findings" value={analysis.total_findings} />
          <SummaryStat label="High severity" value={analysis.high_severity_findings} />
          {completedAt && <SummaryStat label="Completed" value={completedAt} />}
        </dl>

        {analysis.provider && (
          <p className="text-xs text-slate-400">
            {analysis.provider}
            {analysis.model_name ? ` · ${analysis.model_name}` : ''}
          </p>
        )}
      </Link>
    </Card>
  )
}
