import { apiClient } from '@/api/client'
import type { AnalysisCreateResult, AnalysisSummary } from '@/types/api'

export async function listRecentAnalyses(limit = 10): Promise<AnalysisSummary[]> {
  const response = await apiClient.get<AnalysisSummary[]>('/ai/analyses', {
    params: { limit },
  })

  return response.data
}

export async function createAnalysisFromDocuments(
  clinicalDocumentIds: number[],
): Promise<AnalysisCreateResult> {
  const response = await apiClient.post<AnalysisCreateResult>('/ai/summarize', {
    clinical_document_ids: clinicalDocumentIds,
  })

  return response.data
}
