import { apiClient } from '@/api/client'
import type { Medication } from '@/types/api'

// A self-maintained medication list is always the user's own report, never
// something extracted from a document, so this is fixed rather than a
// user-facing field (see docs/data-model.md's description of the Medication
// model as independent of document extraction).
const SOURCE = 'patient_reported'

export interface MedicationPayload {
  medicationName: string
  dose: string
  route: string
  frequency: string
  status: string
  notes: string
}

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

export async function listMedications(): Promise<Medication[]> {
  const response = await apiClient.get<Medication[]>('/medications')
  return response.data
}

export async function createMedication(payload: MedicationPayload): Promise<Medication> {
  const response = await apiClient.post<Medication>('/medications', toRequestBody(payload))
  return response.data
}

export async function updateMedication(
  id: number,
  payload: MedicationPayload,
): Promise<Medication> {
  const response = await apiClient.patch<Medication>(`/medications/${id}`, toRequestBody(payload))
  return response.data
}

export async function deleteMedication(id: number): Promise<void> {
  await apiClient.delete(`/medications/${id}`)
}
