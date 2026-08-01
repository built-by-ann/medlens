import { cn } from '@/utils/cn'
import { RESOLUTION_STATUS_LABELS } from '@/utils/discrepancy'
import type { ResolutionStatus } from '@/types/api'

const RESOLUTION_STATUS_STYLES: Record<ResolutionStatus, string> = {
  open: 'bg-surface-hover text-foreground',
  reviewed: 'bg-info-badge text-badge-foreground',
  resolved: 'bg-success-badge text-badge-foreground',
  dismissed: 'bg-surface-hover text-muted',
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
