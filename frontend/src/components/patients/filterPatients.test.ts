import { describe, expect, it } from 'vitest'
import { filterPatients } from '@/components/patients/filterPatients'
import type { Patient } from '@/types/api'

function makePatient(overrides: Partial<Patient>): Patient {
  return {
    id: 1,
    user_id: 1,
    first_name: 'Jane',
    last_name: 'Doe',
    date_of_birth: '1980-05-14',
    external_mrn: null,
    status: 'active',
    notes: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    ...overrides,
  }
}

describe('filterPatients', () => {
  const patients = [
    makePatient({ id: 1, first_name: 'Jane', last_name: 'Doe', external_mrn: 'MRN-001' }),
    makePatient({ id: 2, first_name: 'John', last_name: 'Smith', external_mrn: null }),
  ]

  it('returns every patient when the search term is empty', () => {
    expect(filterPatients(patients, '')).toEqual(patients)
  })

  it('returns every patient when the search term is only whitespace', () => {
    expect(filterPatients(patients, '   ')).toEqual(patients)
  })

  it('matches by first name, case-insensitively', () => {
    expect(filterPatients(patients, 'jane')).toEqual([patients[0]])
  })

  it('matches by last name, case-insensitively', () => {
    expect(filterPatients(patients, 'SMITH')).toEqual([patients[1]])
  })

  it('matches by full name', () => {
    expect(filterPatients(patients, 'jane doe')).toEqual([patients[0]])
  })

  it('matches by external MRN when present', () => {
    expect(filterPatients(patients, 'mrn-001')).toEqual([patients[0]])
  })

  it('does not match patients with no MRN against an MRN-shaped term', () => {
    expect(filterPatients(patients, 'mrn-999')).toEqual([])
  })

  it('returns an empty array when nothing matches', () => {
    expect(filterPatients(patients, 'nonexistent')).toEqual([])
  })

  it('does not mutate the input array', () => {
    const original = [...patients]
    filterPatients(patients, 'jane')
    expect(patients).toEqual(original)
  })
})
