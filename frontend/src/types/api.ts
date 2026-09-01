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
  username: string | null
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
  // Unlike the four counts above (fixed at analysis completion), this is
  // recomputed on every request from the discrepancies' current
  // resolution_status; it drops as a provider resolves/dismisses findings.
  open_findings: number
  provider: string | null
  model_name: string | null
}

// Just enough to identify a patient inline in another resource's response -
// e.g. which patient a cross-patient analysis belongs to (Issue #157).
export interface PatientSummary {
  id: number
  first_name: string
  last_name: string
}

// The Dashboard's Recent Analyses feed (Issue #157) is the one place an
// analysis is shown outside a single patient's own pages, so, unlike
// AnalysisSummary, the patient it belongs to isn't already established by
// the URL and has to be identified inline.
export interface RecentAnalysis extends AnalysisSummary {
  patient: PatientSummary
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

// What a provider actually did to resolve a discrepancy, distinct from
// ResolutionStatus (the coarser open/resolved/dismissed state that
// results). Which actions are valid depends on the discrepancy's
// DiscrepancyType; see discrepancyResolutionActions.ts.
export type ResolutionAction = 'add_medication' | 'update_medication' | 'dismiss'

// Who resolved a discrepancy, a minimal, purpose-built view of the
// resolving user for this one nested use, not a general-purpose user type.
export interface ResolvedBy {
  id: number
  name: string | null
  username: string | null
  email: string
}

// POST .../discrepancies/{id}/resolve request body. Every medication field
// is optional at the type level since which ones are required depends on
// `action` (add_medication needs all five; update_medication needs at
// least one; dismiss needs none); see discrepancyResolutionActions.ts,
// which is what actually builds one of these per action/type combination.
export interface DiscrepancyResolutionPayload {
  action: ResolutionAction
  medication_name?: string
  dose?: string
  route?: string
  frequency?: string
  status?: string
  note?: string
}

export interface ClinicalDocumentSummary {
  id: number
  title: string
  document_type: string
}

// MedicationMention has no API exposure of its own; this only exists
// nested inside a MedicationDiscrepancy as supporting evidence (Issue #46).
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
  // Audit trail: all four stay null until resolution_status leaves "open".
  resolution_action: ResolutionAction | null
  resolved_at: string | null
  resolution_note: string | null
  resolved_by: ResolvedBy | null
  created_at: string
  updated_at: string | null
  // Issue #46: supporting evidence nested inline. Either, both, or neither
  // may be present, matching the nullability of medication_id/medication_mention_id.
  medication: Medication | null
  medication_mention: MedicationMentionEvidence | null
}

// The AI's raw, unstructured per-medication observation from the summary
// pass, distinct from Medication (the reconciliation engine's structured
// record) and from MedicationDiscrepancy (a reconciliation finding).
export interface AnalysisMedicationMention {
  id: number
  medication_name: string
  dosage: string | null
  route: string | null
  frequency: string | null
  status: string | null
  notes: string | null
}

// One of the AI's free-text "worth a follow-up" observations from the
// summary pass. Rendered as a follow-up question checklist (Issue #47).
export interface AnalysisInconsistency {
  id: number
  description: string
}

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
  // Issue #47: how many clinical documents this analysis covers, shown in
  // the AI Summary section's metadata.
  document_count: number
  // Issue #47: the AI's raw, unstructured observations, now rendered in a
  // visually distinct "AI Summary" section alongside the deterministic
  // medication_discrepancies findings below.
  medication_mentions: AnalysisMedicationMention[]
  possible_inconsistencies: AnalysisInconsistency[]
  // Issue #148 (and the reconciliation engine it wires up): the deterministic
  // findings, always present as an empty array rather than omitted.
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
