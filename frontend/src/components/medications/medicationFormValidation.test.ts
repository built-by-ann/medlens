import { describe, expect, it } from 'vitest'
import {
  validateMedicationForm,
  EMPTY_MEDICATION_PAYLOAD,
} from '@/components/medications/medicationFormValidation'
import type { MedicationPayload } from '@/api/medications'

const validPayload: MedicationPayload = {
  medicationName: 'Lisinopril',
  dose: '10mg',
  route: 'oral',
  frequency: 'once daily',
  status: 'active',
  notes: '',
}

describe('validateMedicationForm', () => {
  it('returns no errors for a fully valid payload', () => {
    expect(validateMedicationForm(validPayload)).toEqual({})
  })

  it('requires medication name, dose, route, frequency, and status', () => {
    expect(validateMedicationForm(EMPTY_MEDICATION_PAYLOAD)).toEqual({
      medicationName: 'Medication name is required.',
      dose: 'Dosage is required.',
      route: 'Route is required.',
      frequency: 'Frequency is required.',
      status: 'Status is required.',
    })
  })

  it('treats a whitespace-only value as missing', () => {
    expect(validateMedicationForm({ ...validPayload, dose: '   ' })).toEqual({
      dose: 'Dosage is required.',
    })
  })

  it('does not require notes', () => {
    expect(validateMedicationForm({ ...validPayload, notes: '' })).toEqual({})
  })

  it('reports only the fields that are actually missing', () => {
    expect(validateMedicationForm({ ...validPayload, route: '' })).toEqual({
      route: 'Route is required.',
    })
  })
})
