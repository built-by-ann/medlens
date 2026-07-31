import { describe, expect, it } from 'vitest'
import {
  validatePatientForm,
  EMPTY_PATIENT_PAYLOAD,
} from '@/components/patients/patientFormValidation'
import type { PatientPayload } from '@/api/patients'

const validPayload: PatientPayload = {
  firstName: 'Jane',
  lastName: 'Doe',
  dateOfBirth: '1980-05-14',
  externalMrn: '',
  notes: '',
}

describe('validatePatientForm', () => {
  it('returns no errors for a fully valid payload', () => {
    expect(validatePatientForm(validPayload)).toEqual({})
  })

  it('requires first name, last name, and date of birth', () => {
    expect(validatePatientForm(EMPTY_PATIENT_PAYLOAD)).toEqual({
      firstName: 'First name is required.',
      lastName: 'Last name is required.',
      dateOfBirth: 'Date of birth is required.',
    })
  })

  it('treats a whitespace-only value as missing', () => {
    expect(validatePatientForm({ ...validPayload, firstName: '   ' })).toEqual({
      firstName: 'First name is required.',
    })
  })

  it('does not require external MRN or notes', () => {
    expect(validatePatientForm({ ...validPayload, externalMrn: '', notes: '' })).toEqual({})
  })

  it('reports only the fields that are actually missing', () => {
    expect(validatePatientForm({ ...validPayload, lastName: '' })).toEqual({
      lastName: 'Last name is required.',
    })
  })
})
