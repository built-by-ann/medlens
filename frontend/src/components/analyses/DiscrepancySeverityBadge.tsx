import { cn } from '@/utils/cn'
import { DISCREPANCY_SEVERITY_LABELS } from '@/utils/discrepancy'
import type { DiscrepancySeverity } from '@/types/api'

// Severity is always communicated via this visible text label ("High
// severity", not just a red dot), never by badge color alone.
const SEVERITY_BADGE_STYLES: Record<DiscrepancySeverity, string> = {
  high: 'bg-red-100 text-red-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-slate-100 text-slate-700',
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
