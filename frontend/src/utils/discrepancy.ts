import type { DiscrepancySeverity, DiscrepancyType, ResolutionStatus } from '@/types/api'

export const DISCREPANCY_TYPE_LABELS: Record<DiscrepancyType, string> = {
  missing_from_medication_list: 'Missing from medication list',
  discontinued_status_conflict: 'Discontinued status conflict',
  dose_conflict: 'Dose conflict',
  route_conflict: 'Route conflict',
  frequency_conflict: 'Frequency conflict',
  status_conflict: 'Status conflict',
  unsupported_medication_list_entry: 'Unsupported medication list entry',
}

export function discrepancyTypeLabel(type: DiscrepancyType): string {
  return DISCREPANCY_TYPE_LABELS[type]
}

export const DISCREPANCY_SEVERITY_LABELS: Record<DiscrepancySeverity, string> = {
  high: 'High severity',
  medium: 'Medium severity',
  low: 'Low severity',
}

export function discrepancySeverityLabel(severity: DiscrepancySeverity): string {
  return DISCREPANCY_SEVERITY_LABELS[severity]
}

// Lower is more severe, so findings can be sorted highest-severity-first.
// There is no "critical" tier: DiscrepancySeverity (backend enum, unchanged
// by this issue) only ever has high/medium/low; see docs/frontend.md for
// why a 4th tier was not invented to match the issue's example wording.
export const DISCREPANCY_SEVERITY_RANK: Record<DiscrepancySeverity, number> = {
  high: 0,
  medium: 1,
  low: 2,
}

export const RESOLUTION_STATUS_LABELS: Record<ResolutionStatus, string> = {
  open: 'Open',
  reviewed: 'In Review',
  resolved: 'Resolved',
  dismissed: 'Dismissed',
}

export function resolutionStatusLabel(status: ResolutionStatus): string {
  return RESOLUTION_STATUS_LABELS[status]
}
