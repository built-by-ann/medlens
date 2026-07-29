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
}

export interface AnalysisCreateResult {
  analysis_id: number
  provider: string
  model: string
  summary: string
  possible_inconsistencies: string[]
}

export interface AnalysisMedicationMention {
  id: number
  medication_name: string
  dosage: string | null
  route: string | null
  frequency: string | null
  status: string | null
  notes: string | null
}

export interface AnalysisInconsistency {
  id: number
  description: string
}

export type DiscrepancyType =
  | 'missing_from_medication_list'
  | 'discontinued_status_conflict'
  | 'dose_conflict'
  | 'route_conflict'
  | 'frequency_conflict'
  | 'status_conflict'
  | 'unsupported_medication_list_entry'

export type DiscrepancySeverity = 'low' | 'medium' | 'high'

export type ResolutionStatus = 'open' | 'reviewed' | 'resolved' | 'dismissed'

export interface ClinicalDocumentSummary {
  id: number
  title: string
  document_type: string
}

// MedicationMention has no API exposure of its own - this only exists
// nested inside a MedicationDiscrepancy as supporting evidence.
export interface MedicationMentionEvidence {
  id: number
  medication_name: string
  dose: string | null
  route: string | null
  frequency: string | null
  status: string | null
  context_text: string | null
  clinical_document: ClinicalDocumentSummary
}

export interface MedicationDiscrepancy {
  id: number
  analysis_id: number
  medication_id: number | null
  medication_mention_id: number | null
  discrepancy_type: DiscrepancyType
  severity: DiscrepancySeverity
  title: string
  ai_explanation: string | null
  recommendation: string | null
  expected_value: string | null
  observed_value: string | null
  resolution_status: ResolutionStatus
  created_at: string
  updated_at: string | null
  medication: Medication | null
  medication_mention: MedicationMentionEvidence | null
}

// AnalysisDetail was deliberately narrower than the backend's
// AnalysisDetailResponse in Sprint 3.5, omitting medication_mentions,
// possible_inconsistencies, and medication_discrepancies (the AI's raw
// findings and the reconciliation engine's structured findings) so it was
// structurally impossible to accidentally render that UI before its time.
// Issue #45 is that future issue, so this now mirrors the backend response
// in full.
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
  document_count: number
  medication_mentions: AnalysisMedicationMention[]
  possible_inconsistencies: AnalysisInconsistency[]
  medication_discrepancies: MedicationDiscrepancy[]
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
