import type { PatientPayload } from '@/api/patients'

export type PatientFormErrors = Partial<Record<keyof PatientPayload, string>>

// Mirrors the backend's own validation exactly (schemas/patient.py):
// first_name, last_name, and date_of_birth are required; external_mrn and
// notes are optional.
export function validatePatientForm(values: PatientPayload): PatientFormErrors {
  const errors: PatientFormErrors = {}

  if (!values.firstName.trim()) errors.firstName = 'First name is required.'
  if (!values.lastName.trim()) errors.lastName = 'Last name is required.'
  if (!values.dateOfBirth.trim()) errors.dateOfBirth = 'Date of birth is required.'

  return errors
}

export const EMPTY_PATIENT_PAYLOAD: PatientPayload = {
  firstName: '',
  lastName: '',
  dateOfBirth: '',
  externalMrn: '',
  notes: '',
}
