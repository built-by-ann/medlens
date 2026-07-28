import { apiClient } from '@/api/client'
import type { AnalysisSummary } from '@/types/api'

export async function listRecentAnalyses(limit = 10): Promise<AnalysisSummary[]> {
  const response = await apiClient.get<AnalysisSummary[]>('/ai/analyses', {
    params: { limit },
  })

  return response.data
}
