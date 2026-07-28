import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { usePatientMedications } from '@/hooks/usePatientMedications'
import {
  createMedication,
  deleteMedication,
  listMedications,
  updateMedication,
} from '@/api/medications'
import type { Medication } from '@/types/api'

vi.mock('@/api/medications', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/medications')>()

  return {
    ...actual,
    listMedications: vi.fn(),
    createMedication: vi.fn(),
    updateMedication: vi.fn(),
    deleteMedication: vi.fn(),
  }
})

const mockedListMedications = vi.mocked(listMedications)
const mockedCreateMedication = vi.mocked(createMedication)
const mockedUpdateMedication = vi.mocked(updateMedication)
const mockedDeleteMedication = vi.mocked(deleteMedication)

const samplePayload = {
  medicationName: 'Lisinopril',
  dose: '10 mg',
  route: 'oral',
  frequency: 'once daily',
  status: 'active',
  notes: '',
}

function makeMedication(overrides: Partial<Medication> = {}): Medication {
  return {
    id: 1,
    patient_id: 42,
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

const sampleMedication = makeMedication()

describe('usePatientMedications', () => {
  beforeEach(() => {
    mockedListMedications.mockReset()
    mockedCreateMedication.mockReset()
    mockedUpdateMedication.mockReset()
    mockedDeleteMedication.mockReset()
  })

  it('starts in a loading state with no medications and no error', () => {
    mockedListMedications.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => usePatientMedications(42))

    expect(result.current.isLoading).toBe(true)
    expect(result.current.medications).toEqual([])
    expect(result.current.error).toBeNull()
  })

  it('fetches medications scoped to the given patientId', async () => {
    mockedListMedications.mockResolvedValue([sampleMedication])

    const { result } = renderHook(() => usePatientMedications(42))

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.medications).toEqual([sampleMedication])
    expect(mockedListMedications).toHaveBeenCalledWith(42)
  })

  it('exposes the error message when the initial fetch fails', async () => {
    mockedListMedications.mockRejectedValue({ status: 500, message: 'Something went wrong.' })

    const { result } = renderHook(() => usePatientMedications(42))

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBe('Something went wrong.')
  })

  it('retry() re-fetches and can recover from a previous error', async () => {
    mockedListMedications.mockRejectedValueOnce({ status: 500, message: 'Server error.' })
    mockedListMedications.mockResolvedValueOnce([sampleMedication])

    const { result } = renderHook(() => usePatientMedications(42))

    await waitFor(() => expect(result.current.error).toBe('Server error.'))

    act(() => {
      result.current.retry()
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBeNull()
    expect(result.current.medications).toEqual([sampleMedication])
    expect(mockedListMedications).toHaveBeenCalledTimes(2)
  })

  it('re-fetches when patientId changes, so switching patients never shows stale data', async () => {
    mockedListMedications.mockResolvedValueOnce([makeMedication({ id: 1, patient_id: 42 })])
    mockedListMedications.mockResolvedValueOnce([makeMedication({ id: 2, patient_id: 99 })])

    const { result, rerender } = renderHook(({ patientId }) => usePatientMedications(patientId), {
      initialProps: { patientId: 42 },
    })

    await waitFor(() =>
      expect(result.current.medications).toEqual([expect.objectContaining({ id: 1 })]),
    )

    rerender({ patientId: 99 })

    await waitFor(() =>
      expect(result.current.medications).toEqual([expect.objectContaining({ id: 2 })]),
    )
    expect(mockedListMedications).toHaveBeenNthCalledWith(1, 42)
    expect(mockedListMedications).toHaveBeenNthCalledWith(2, 99)
  })

  it('addMedication prepends the created medication to local state, scoped to patientId', async () => {
    mockedListMedications.mockResolvedValue([])
    mockedCreateMedication.mockResolvedValue(sampleMedication)

    const { result } = renderHook(() => usePatientMedications(42))
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.addMedication(samplePayload)
    })

    expect(result.current.medications).toEqual([sampleMedication])
    expect(mockedCreateMedication).toHaveBeenCalledWith(42, samplePayload)
  })

  it('addMedication propagates the error without changing local state', async () => {
    mockedListMedications.mockResolvedValue([])
    mockedCreateMedication.mockRejectedValue({ status: 500, message: 'Create failed.' })

    const { result } = renderHook(() => usePatientMedications(42))
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await expect(
      act(async () => {
        await result.current.addMedication(samplePayload)
      }),
    ).rejects.toMatchObject({ message: 'Create failed.' })
    expect(result.current.medications).toEqual([])
  })

  it('editMedication replaces the matching medication in local state', async () => {
    mockedListMedications.mockResolvedValue([sampleMedication])
    const updated = { ...sampleMedication, dose: '20 mg' }
    mockedUpdateMedication.mockResolvedValue(updated)

    const { result } = renderHook(() => usePatientMedications(42))
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.editMedication(1, { ...samplePayload, dose: '20 mg' })
    })

    expect(result.current.medications).toEqual([updated])
    expect(mockedUpdateMedication).toHaveBeenCalledWith(42, 1, { ...samplePayload, dose: '20 mg' })
  })

  it('removeMedication removes the matching medication from local state', async () => {
    mockedListMedications.mockResolvedValue([sampleMedication])
    mockedDeleteMedication.mockResolvedValue(undefined)

    const { result } = renderHook(() => usePatientMedications(42))
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.removeMedication(1)
    })

    expect(result.current.medications).toEqual([])
    expect(mockedDeleteMedication).toHaveBeenCalledWith(42, 1)
  })

  it('removeMedication propagates the error without changing local state', async () => {
    mockedListMedications.mockResolvedValue([sampleMedication])
    mockedDeleteMedication.mockRejectedValue({ status: 500, message: 'Delete failed.' })

    const { result } = renderHook(() => usePatientMedications(42))
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await expect(
      act(async () => {
        await result.current.removeMedication(1)
      }),
    ).rejects.toMatchObject({ message: 'Delete failed.' })
    expect(result.current.medications).toEqual([sampleMedication])
  })
})
