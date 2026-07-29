import { apiClient } from '@/api/client'
import type { AnalysisCreateResult, AnalysisDetail, AnalysisSummary } from '@/types/api'

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

export async function getAnalysisDetail(
  patientId: number,
  analysisId: number,
): Promise<AnalysisDetail> {
  const response = await apiClient.get<AnalysisDetail>(
    `/patients/${patientId}/analyses/${analysisId}`,
  )

  return response.data
}

export async function deleteAnalysis(patientId: number, analysisId: number): Promise<void> {
  await apiClient.delete(`/patients/${patientId}/analyses/${analysisId}`)
}
