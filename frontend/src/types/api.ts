/**
 * Frontend representations of backend response models.
 *
 * These mirror the Pydantic response schemas documented in docs/api.md and
 * are added to incrementally as each backend resource is wired up on the
 * frontend. They intentionally do not cover every backend model yet.
 */

export interface User {
  id: number
  email: string
  name: string | null
  created_at: string
}

export interface AuthToken {
  access_token: string
  token_type: string
}

export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface AnalysisSummary {
  id: number
  status: AnalysisStatus
  created_at: string
  completed_at: string | null
  error_message: string | null
  summary: string | null
  document_count: number
  total_findings: number
  high_severity_findings: number
  medium_severity_findings: number
  low_severity_findings: number
  provider: string | null
  model_name: string | null
}

export interface ClinicalDocument {
  id: number
  user_id: number
  document_type: string
  title: string
  raw_text: string
  file_name: string | null
  file_type: string | null
  created_at: string
  updated_at: string | null
}

export interface AnalysisCreateResult {
  analysis_id: number
  provider: string
  model: string
  summary: string
  possible_inconsistencies: string[]
}
