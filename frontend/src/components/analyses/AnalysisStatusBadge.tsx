import { cn } from '@/utils/cn'
import { ANALYSIS_STATUS_LABELS } from '@/utils/analysisStatus'
import type { AnalysisStatus } from '@/types/api'

// Status is always communicated via this visible text label, never by
// badge color alone.
const STATUS_BADGE_STYLES: Record<AnalysisStatus, string> = {
  pending: 'bg-slate-100 text-slate-700',
  processing: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}

interface AnalysisStatusBadgeProps {
  status: AnalysisStatus
}

export function AnalysisStatusBadge({ status }: AnalysisStatusBadgeProps) {
  return (
    <span
      className={cn('rounded-full px-2 py-0.5 text-xs font-medium', STATUS_BADGE_STYLES[status])}
    >
      {ANALYSIS_STATUS_LABELS[status]}
    </span>
  )
}
