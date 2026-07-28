import { apiClient } from '@/api/client'
import type { Patient } from '@/types/api'

export interface PatientPayload {
  firstName: string
  lastName: string
  dateOfBirth: string
  externalMrn: string
  notes: string
}

function toRequestBody(payload: PatientPayload) {
  const trimmedMrn = payload.externalMrn.trim()
  const trimmedNotes = payload.notes.trim()

  return {
    first_name: payload.firstName.trim(),
    last_name: payload.lastName.trim(),
    date_of_birth: payload.dateOfBirth,
    external_mrn: trimmedMrn ? trimmedMrn : null,
    notes: trimmedNotes ? trimmedNotes : null,
  }
}

export async function listPatients(): Promise<Patient[]> {
  const response = await apiClient.get<Patient[]>('/patients')
  return response.data
}

export async function getPatient(id: number): Promise<Patient> {
  const response = await apiClient.get<Patient>(`/patients/${id}`)
  return response.data
}

export async function createPatient(payload: PatientPayload): Promise<Patient> {
  const response = await apiClient.post<Patient>('/patients', toRequestBody(payload))
  return response.data
}

export async function updatePatient(id: number, payload: PatientPayload): Promise<Patient> {
  const response = await apiClient.patch<Patient>(`/patients/${id}`, toRequestBody(payload))
  return response.data
}

export async function archivePatient(id: number): Promise<void> {
  await apiClient.delete(`/patients/${id}`)
}
