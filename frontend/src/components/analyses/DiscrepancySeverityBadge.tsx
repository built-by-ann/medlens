import { cn } from '@/utils/cn'
import { DISCREPANCY_SEVERITY_LABELS } from '@/utils/discrepancy'
import type { DiscrepancySeverity } from '@/types/api'

// Severity is always communicated via this visible text label ("High
// severity", not just a colored dot), never by badge color alone.
const SEVERITY_BADGE_STYLES: Record<DiscrepancySeverity, string> = {
  high: 'bg-danger-badge text-badge-foreground',
  medium: 'bg-warning-badge text-badge-foreground',
  low: 'bg-surface-hover text-foreground',
}

interface DiscrepancySeverityBadgeProps {
  severity: DiscrepancySeverity
}

export function DiscrepancySeverityBadge({ severity }: DiscrepancySeverityBadgeProps) {
  return (
    <span
      className={cn(
        'rounded-full px-2 py-0.5 text-xs font-medium',
        SEVERITY_BADGE_STYLES[severity],
      )}
    >
      {DISCREPANCY_SEVERITY_LABELS[severity]}
    </span>
  )
}
