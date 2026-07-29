import { describe, expect, it } from 'vitest'
import { sortPatientsByRecentActivity } from '@/components/patients/sortPatientsByRecentActivity'
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

describe('sortPatientsByRecentActivity', () => {
  it('orders by updated_at descending when every patient has one', () => {
    const older = makePatient({ id: 1, updated_at: '2026-01-01T00:00:00Z' })
    const newer = makePatient({ id: 2, updated_at: '2026-02-01T00:00:00Z' })

    expect(sortPatientsByRecentActivity([older, newer], 10)).toEqual([newer, older])
  })

  it('falls back to created_at for a patient with no updated_at', () => {
    const neverUpdated = makePatient({
      id: 1,
      created_at: '2026-03-01T00:00:00Z',
      updated_at: null,
    })
    const updatedEarlier = makePatient({
      id: 2,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-02-01T00:00:00Z',
    })

    // neverUpdated's own created_at (March) is more recent than
    // updatedEarlier's updated_at (February), so it sorts first.
    expect(sortPatientsByRecentActivity([updatedEarlier, neverUpdated], 10)).toEqual([
      neverUpdated,
      updatedEarlier,
    ])
  })

  it('limits the result to the given count', () => {
    const patients = [
      makePatient({ id: 1, created_at: '2026-01-01T00:00:00Z' }),
      makePatient({ id: 2, created_at: '2026-01-02T00:00:00Z' }),
      makePatient({ id: 3, created_at: '2026-01-03T00:00:00Z' }),
    ]

    const result = sortPatientsByRecentActivity(patients, 2)

    expect(result).toHaveLength(2)
    expect(result.map((patient) => patient.id)).toEqual([3, 2])
  })

  it('does not mutate the input array', () => {
    const patients = [
      makePatient({ id: 1, created_at: '2026-01-01T00:00:00Z' }),
      makePatient({ id: 2, created_at: '2026-01-02T00:00:00Z' }),
    ]
    const original = [...patients]

    sortPatientsByRecentActivity(patients, 10)

    expect(patients).toEqual(original)
  })

  it('returns an empty array when given no patients', () => {
    expect(sortPatientsByRecentActivity([], 5)).toEqual([])
  })
})
