import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { usePatients } from '@/hooks/usePatients'
import { archivePatient, listPatients } from '@/api/patients'
import type { Patient } from '@/types/api'

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    listPatients: vi.fn(),
    archivePatient: vi.fn(),
  }
})

const mockedListPatients = vi.mocked(listPatients)
const mockedArchivePatient = vi.mocked(archivePatient)

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

describe('usePatients', () => {
  beforeEach(() => {
    mockedListPatients.mockReset()
    mockedArchivePatient.mockReset()
  })

  it('starts in a loading state with no patients and no error', () => {
    mockedListPatients.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => usePatients())

    expect(result.current.isLoading).toBe(true)
    expect(result.current.patients).toEqual([])
    expect(result.current.error).toBeNull()
  })

  it('resolves with the fetched patients', async () => {
    mockedListPatients.mockResolvedValue([samplePatient])

    const { result } = renderHook(() => usePatients())

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.patients).toEqual([samplePatient])
  })

  it('exposes the error message when the initial fetch fails', async () => {
    mockedListPatients.mockRejectedValue({ status: 500, message: 'Something went wrong.' })

    const { result } = renderHook(() => usePatients())

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBe('Something went wrong.')
  })

  it('retry() re-fetches and can recover from a previous error', async () => {
    mockedListPatients.mockRejectedValueOnce({ status: 500, message: 'Server error.' })
    mockedListPatients.mockResolvedValueOnce([samplePatient])

    const { result } = renderHook(() => usePatients())

    await waitFor(() => expect(result.current.error).toBe('Server error.'))

    act(() => {
      result.current.retry()
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBeNull()
    expect(result.current.patients).toEqual([samplePatient])
    expect(mockedListPatients).toHaveBeenCalledTimes(2)
  })

  it('archivePatient removes the matching patient from local state', async () => {
    mockedListPatients.mockResolvedValue([samplePatient])
    mockedArchivePatient.mockResolvedValue(undefined)

    const { result } = renderHook(() => usePatients())
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.archivePatient(1)
    })

    expect(result.current.patients).toEqual([])
  })

  it('archivePatient propagates the error without changing local state', async () => {
    mockedListPatients.mockResolvedValue([samplePatient])
    mockedArchivePatient.mockRejectedValue({ status: 500, message: 'Archive failed.' })

    const { result } = renderHook(() => usePatients())
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await expect(
      act(async () => {
        await result.current.archivePatient(1)
      }),
    ).rejects.toMatchObject({ message: 'Archive failed.' })
    expect(result.current.patients).toEqual([samplePatient])
  })
})
