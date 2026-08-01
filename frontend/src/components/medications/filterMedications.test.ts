import { describe, expect, it } from 'vitest'
import { filterMedications } from '@/components/medications/filterMedications'
import type { Medication } from '@/types/api'

function makeMedication(overrides: Partial<Medication> = {}): Medication {
  return {
    id: 1,
    patient_id: 7,
    medication_name: 'Lisinopril',
    dose: '10 mg',
    route: 'oral',
    frequency: 'once daily',
    status: 'active',
    source: 'patient_reported',
    notes: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    ...overrides,
  }
}

describe('filterMedications', () => {
  const medications = [
    makeMedication({
      id: 1,
      medication_name: 'Lisinopril',
      dose: '10 mg',
      route: 'oral',
      frequency: 'once daily',
      status: 'active',
    }),
    makeMedication({
      id: 2,
      medication_name: 'Atorvastatin',
      dose: '40 mg',
      route: 'oral',
      frequency: 'nightly',
      status: 'discontinued',
    }),
  ]

  it('returns every medication when the search term is empty', () => {
    expect(filterMedications(medications, '')).toEqual(medications)
  })

  it('returns every medication when the search term is only whitespace', () => {
    expect(filterMedications(medications, '   ')).toEqual(medications)
  })

  it('matches by medication name, case-insensitively', () => {
    expect(filterMedications(medications, 'lisino')).toEqual([medications[0]])
  })

  it('matches by dose', () => {
    expect(filterMedications(medications, '40 mg')).toEqual([medications[1]])
  })

  it('matches by route', () => {
    expect(filterMedications(medications, 'oral')).toEqual(medications)
  })

  it('matches by frequency', () => {
    expect(filterMedications(medications, 'nightly')).toEqual([medications[1]])
  })

  it('matches by status', () => {
    expect(filterMedications(medications, 'discontinued')).toEqual([medications[1]])
  })

  it('returns an empty array when nothing matches', () => {
    expect(filterMedications(medications, 'nonexistent')).toEqual([])
  })

  it('does not mutate the input array', () => {
    const original = [...medications]
    filterMedications(medications, 'lisino')
    expect(medications).toEqual(original)
  })
})
