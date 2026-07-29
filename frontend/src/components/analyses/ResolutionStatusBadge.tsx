import { cn } from '@/utils/cn'
import { RESOLUTION_STATUS_LABELS } from '@/utils/discrepancy'
import type { ResolutionStatus } from '@/types/api'

const RESOLUTION_STATUS_STYLES: Record<ResolutionStatus, string> = {
  open: 'bg-slate-100 text-slate-700',
  reviewed: 'bg-blue-100 text-blue-700',
  resolved: 'bg-green-100 text-green-700',
  dismissed: 'bg-slate-100 text-slate-500',
}

interface ResolutionStatusBadgeProps {
  status: ResolutionStatus
}

export function ResolutionStatusBadge({ status }: ResolutionStatusBadgeProps) {
  return (
    <span
      className={cn(
        'rounded-full px-2 py-0.5 text-xs font-medium',
        RESOLUTION_STATUS_STYLES[status],
      )}
    >
      {RESOLUTION_STATUS_LABELS[status]}
    </span>
  )
}
