import { apiClient } from '@/api/client'
import type { ClinicalDocument } from '@/types/api'

// The backend's document_type column is free text (no enum at the schema
// or model level), but the reconciliation engine only recognizes
// "medication_list"/"medication_reconciliation_form" specially, and the
// product docs (README, docs/data-model.md) consistently describe exactly
// these five kinds of clinical note. This is that same fixed vocabulary,
// not an invented one; automatic classification is explicitly out of scope
// here, so the user always chooses.
export interface DocumentTypeOption {
  value: string
  label: string
}

export const DOCUMENT_TYPES: DocumentTypeOption[] = [
  { value: 'visit_note', label: 'Visit note' },
  { value: 'progress_note', label: 'Progress note' },
  { value: 'discharge_summary', label: 'Discharge summary' },
  { value: 'medication_list', label: 'Medication list' },
  { value: 'medication_reconciliation_form', label: 'Medication reconciliation form' },
]

export const DEFAULT_DOCUMENT_TYPE = 'visit_note'

export function documentTypeLabel(value: string): string {
  return DOCUMENT_TYPES.find((type) => type.value === value)?.label ?? value
}

// Matches the backend's own validation exactly (app/api/routes/
// clinical_documents.py): each upload endpoint accepts a file if its
// extension OR its content type matches, whichever is present. A CSV here
// (Issue #164) is just another document format alongside .txt/.pdf - it's
// stored and analyzed as plain evidence text, never parsed into structured
// rows or imported into the patient's medication list the way
// MedicationCsvUpload/api/medications.ts's importMedications does.
export const SUPPORTED_FILE_EXTENSIONS = ['.txt', '.pdf', '.csv']
const SUPPORTED_MIME_TYPES = ['text/plain', 'application/pdf', 'text/csv']

export function isSupportedFileType(file: File): boolean {
  const name = file.name.toLowerCase()
  const hasSupportedExtension = SUPPORTED_FILE_EXTENSIONS.some((extension) =>
    name.endsWith(extension),
  )

  return hasSupportedExtension || SUPPORTED_MIME_TYPES.includes(file.type)
}

function isPdf(file: File): boolean {
  return file.name.toLowerCase().endsWith('.pdf') || file.type === 'application/pdf'
}

export function isCsv(file: File): boolean {
  return file.name.toLowerCase().endsWith('.csv') || file.type === 'text/csv'
}

export function deriveTitleFromFileName(fileName: string): string {
  const withoutExtension = fileName.replace(/\.[^./]+$/, '').trim()

  return withoutExtension || fileName
}

// The single source of truth for "what title will this queued file get on
// upload" - a provider-edited title if they've set one, otherwise the
// filename-derived default. Shared with findDuplicateExistingTitle
// (utils/queuedFiles.ts) so the same-name warning always reflects exactly
// what's about to be saved, not just the original filename.
export function effectiveFileTitle(fileName: string, title?: string): string {
  return title?.trim() || deriveTitleFromFileName(fileName)
}

export interface CreateNoteFromTextPayload {
  title: string
  rawText: string
  documentType: string
}

export async function createClinicalDocumentFromText(
  patientId: number,
  { title, rawText, documentType }: CreateNoteFromTextPayload,
): Promise<ClinicalDocument> {
  const response = await apiClient.post<ClinicalDocument>(
    `/patients/${patientId}/clinical-documents`,
    {
      document_type: documentType,
      title,
      raw_text: rawText,
    },
  )

  return response.data
}

export async function uploadClinicalDocumentFile(
  patientId: number,
  file: File,
  documentType: string,
  // A provider-edited title, when they've renamed the file's default title
  // (e.g. to resolve a same-name collision with a document already on
  // file). Falls back to the same filename-derived title used everywhere
  // else when unset or blank.
  title?: string,
): Promise<ClinicalDocument> {
  const endpoint = isPdf(file)
    ? `/patients/${patientId}/clinical-documents/upload-pdf`
    : isCsv(file)
      ? `/patients/${patientId}/clinical-documents/upload-csv`
      : `/patients/${patientId}/clinical-documents/upload-txt`

  const formData = new FormData()
  formData.append('document_type', documentType)
  formData.append('title', effectiveFileTitle(file.name, title))
  formData.append('file', file)

  const response = await apiClient.post<ClinicalDocument>(endpoint, formData)

  return response.data
}

export async function listClinicalDocuments(patientId: number): Promise<ClinicalDocument[]> {
  const response = await apiClient.get<ClinicalDocument[]>(
    `/patients/${patientId}/clinical-documents`,
  )

  return response.data
}

export async function deleteClinicalDocument(patientId: number, documentId: number): Promise<void> {
  await apiClient.delete(`/patients/${patientId}/clinical-documents/${documentId}`)
}
