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
  patient_id: number
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
  patient_id: number
  document_type: string
  title: string
  raw_text: string
  file_name: string | null
  file_type: string | null
  created_at: string
  updated_at: string | null
  // How many analyses this document has been included in (Issue #146).
  // There is no file size field: the backend never stores the original
  // uploaded file's bytes, only its extracted raw_text, so there is no
  // real byte size to expose.
  analysis_count: number
}

export interface AnalysisCreateResult {
  analysis_id: number
  provider: string
  model: string
  summary: string
  possible_inconsistencies: string[]
}

// Deliberately narrower than the backend's AnalysisDetailResponse: it also
// returns medication_mentions and possible_inconsistencies (the AI's raw
// findings), but rendering those is the discrepancy/AI-summary UI that
// Sprint 3.5 explicitly defers to a future issue. Omitting the fields here
// makes it structurally impossible to accidentally render them early.
export interface AnalysisDetail {
  id: number
  patient_id: number
  status: AnalysisStatus
  provider: string | null
  model_name: string | null
  summary: string | null
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  created_at: string
  updated_at: string | null
}

export interface Patient {
  id: number
  user_id: number
  first_name: string
  last_name: string
  date_of_birth: string
  external_mrn: string | null
  status: string
  notes: string | null
  created_at: string
  updated_at: string | null
}

export interface Medication {
  id: number
  patient_id: number
  medication_name: string
  dose: string
  route: string
  frequency: string
  status: string
  source: string
  notes: string | null
  created_at: string
  updated_at: string | null
}

export interface MedicationImportSummary {
  rows_processed: number
  medications_created: number
  blank_rows_ignored: number
}

export interface MedicationCsvFieldError {
  field: string
  message: string
}

export interface MedicationCsvRowError {
  row: number
  errors: MedicationCsvFieldError[]
}
