import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { usePatient } from '@/hooks/usePatient'
import { getPatient } from '@/api/patients'
import type { Patient } from '@/types/api'

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    getPatient: vi.fn(),
  }
})

const mockedGetPatient = vi.mocked(getPatient)

const samplePatient: Patient = {
  id: 1,
  user_id: 1,
  first_name: 'Jane',
  last_name: 'Doe',
  date_of_birth: '1980-05-14',
  external_mrn: 'MRN-001',
  status: 'active',
  notes: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
}

describe('usePatient', () => {
  beforeEach(() => {
    mockedGetPatient.mockReset()
  })

  it('starts in a loading state with no patient and no error', () => {
    mockedGetPatient.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => usePatient(1))

    expect(result.current.isLoading).toBe(true)
    expect(result.current.patient).toBeNull()
    expect(result.current.error).toBeNull()
  })

  it('resolves with the fetched patient', async () => {
    mockedGetPatient.mockResolvedValue(samplePatient)

    const { result } = renderHook(() => usePatient(1))

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.patient).toEqual(samplePatient)
    expect(mockedGetPatient).toHaveBeenCalledWith(1)
  })

  it('exposes the error message for a not-found or not-owned patient', async () => {
    mockedGetPatient.mockRejectedValue({ status: 404, message: 'Patient not found' })

    const { result } = renderHook(() => usePatient(999))

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBe('Patient not found')
    expect(result.current.patient).toBeNull()
  })

  it('retry() re-fetches and can recover from a previous error', async () => {
    mockedGetPatient.mockRejectedValueOnce({ status: 500, message: 'Server error.' })
    mockedGetPatient.mockResolvedValueOnce(samplePatient)

    const { result } = renderHook(() => usePatient(1))

    await waitFor(() => expect(result.current.error).toBe('Server error.'))

    act(() => {
      result.current.retry()
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBeNull()
    expect(result.current.patient).toEqual(samplePatient)
    expect(mockedGetPatient).toHaveBeenCalledTimes(2)
  })
})
