import { apiClient } from '@/api/client'
import type { Medication } from '@/types/api'

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
