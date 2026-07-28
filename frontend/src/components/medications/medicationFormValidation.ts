import type { MedicationPayload } from '@/api/medications'

export type MedicationFormErrors = Partial<Record<keyof MedicationPayload, string>>

// Mirrors the backend's own validation exactly (schemas/medication.py):
// medication_name, dose, route, frequency, and status are all required
// non-empty strings; notes is the only optional field.
export function validateMedicationForm(values: MedicationPayload): MedicationFormErrors {
  const errors: MedicationFormErrors = {}

  if (!values.medicationName.trim()) errors.medicationName = 'Medication name is required.'
  if (!values.dose.trim()) errors.dose = 'Dosage is required.'
  if (!values.route.trim()) errors.route = 'Route is required.'
  if (!values.frequency.trim()) errors.frequency = 'Frequency is required.'
  if (!values.status.trim()) errors.status = 'Status is required.'

  return errors
}

export const EMPTY_MEDICATION_PAYLOAD: MedicationPayload = {
  medicationName: '',
  dose: '',
  route: '',
  frequency: '',
  status: '',
  notes: '',
}
