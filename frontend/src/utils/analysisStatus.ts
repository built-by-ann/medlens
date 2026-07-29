import type { AnalysisStatus } from '@/types/api'

export const ANALYSIS_STATUS_LABELS: Record<AnalysisStatus, string> = {
  pending: 'Pending',
  processing: 'Processing',
  completed: 'Completed',
  failed: 'Failed',
}

export function analysisStatusLabel(status: AnalysisStatus): string {
  return ANALYSIS_STATUS_LABELS[status]
}
