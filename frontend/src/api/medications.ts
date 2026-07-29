import { apiClient, type ApiError } from '@/api/client'
import type { Medication, MedicationCsvRowError, MedicationImportSummary } from '@/types/api'

export interface MedicationPayload {
  medicationName: string
  dose: string
  route: string
  frequency: string
  status: string
  notes: string
}

// A self-maintained medication list is always the patient's own report,
// never something extracted from a document, so this is fixed rather than
// a user-facing field (see docs/data-model.md's description of the
// Medication model as independent of document extraction).
const SOURCE = 'patient_reported'

function toRequestBody(payload: MedicationPayload) {
  const trimmedNotes = payload.notes.trim()

  return {
    medication_name: payload.medicationName,
    dose: payload.dose,
    route: payload.route,
    frequency: payload.frequency,
    status: payload.status,
    source: SOURCE,
    notes: trimmedNotes ? trimmedNotes : null,
  }
}

export async function listMedications(patientId: number): Promise<Medication[]> {
  const response = await apiClient.get<Medication[]>(`/patients/${patientId}/medications`)
  return response.data
}

export async function createMedication(
  patientId: number,
  payload: MedicationPayload,
): Promise<Medication> {
  const response = await apiClient.post<Medication>(
    `/patients/${patientId}/medications`,
    toRequestBody(payload),
  )
  return response.data
}

export async function updateMedication(
  patientId: number,
  medicationId: number,
  payload: MedicationPayload,
): Promise<Medication> {
  const response = await apiClient.patch<Medication>(
    `/patients/${patientId}/medications/${medicationId}`,
    toRequestBody(payload),
  )
  return response.data
}

export async function deleteMedication(patientId: number, medicationId: number): Promise<void> {
  await apiClient.delete(`/patients/${patientId}/medications/${medicationId}`)
}

// The one shape of error `POST /patients/{id}/medications/import` returns
// that no other endpoint does: a 422 whose `detail` is an object carrying
// both a summary message and per-row validation errors, rather than a
// plain string or a list of field errors. `ApiError.message` still reads
// correctly on its own (see api/client.ts), but callers that want to show
// row-level detail need this narrowed shape.
export interface MedicationCsvImportError extends ApiError {
  rowErrors?: MedicationCsvRowError[]
}

function getCsvRowErrors(detail: unknown): MedicationCsvRowError[] | undefined {
  if (
    typeof detail === 'object' &&
    detail !== null &&
    'row_errors' in detail &&
    Array.isArray((detail as { row_errors: unknown }).row_errors)
  ) {
    return (detail as { row_errors: MedicationCsvRowError[] }).row_errors
  }

  return undefined
}

export async function importMedicationsCsv(
  patientId: number,
  file: File,
): Promise<MedicationImportSummary> {
  const formData = new FormData()
  // The browser generates the correct multipart boundary for FormData
  // bodies on its own; setting a Content-Type header manually here would
  // overwrite that boundary and break the upload.
  formData.append('file', file)

  try {
    const response = await apiClient.post<MedicationImportSummary>(
      `/patients/${patientId}/medications/import`,
      formData,
    )
    return response.data
  } catch (error) {
    const apiError = error as MedicationCsvImportError
    const rowErrors = getCsvRowErrors(apiError.detail)

    if (rowErrors) {
      throw { ...apiError, rowErrors } satisfies MedicationCsvImportError
    }

    throw error
  }
}
