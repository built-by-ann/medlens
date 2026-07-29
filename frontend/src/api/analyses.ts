import { apiClient } from '@/api/client'
import type { AnalysisCreateResult, AnalysisSummary } from '@/types/api'

export async function listAnalyses(patientId: number, limit = 10): Promise<AnalysisSummary[]> {
  const response = await apiClient.get<AnalysisSummary[]>(`/patients/${patientId}/analyses`, {
    params: { limit },
  })

  return response.data
}

export async function createAnalysisFromDocuments(
  patientId: number,
  clinicalDocumentIds: number[],
): Promise<AnalysisCreateResult> {
  const response = await apiClient.post<AnalysisCreateResult>(`/patients/${patientId}/analyses`, {
    clinical_document_ids: clinicalDocumentIds,
  })

  return response.data
}
