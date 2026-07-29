import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { usePatientClinicalDocuments } from '@/hooks/usePatientClinicalDocuments'
import { deleteClinicalDocument, listClinicalDocuments } from '@/api/clinicalDocuments'
import type { ClinicalDocument } from '@/types/api'

vi.mock('@/api/clinicalDocuments', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/clinicalDocuments')>()

  return {
    ...actual,
    listClinicalDocuments: vi.fn(),
    deleteClinicalDocument: vi.fn(),
  }
})

const mockedListClinicalDocuments = vi.mocked(listClinicalDocuments)
const mockedDeleteClinicalDocument = vi.mocked(deleteClinicalDocument)

function makeDocument(overrides: Partial<ClinicalDocument> = {}): ClinicalDocument {
  return {
    id: 1,
    patient_id: 42,
    document_type: 'visit_note',
    title: 'Initial Visit',
    raw_text: 'Patient presents with hypertension.',
    file_name: null,
    file_type: 'manual_entry',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    analysis_count: 0,
    ...overrides,
  }
}

const sampleDocument = makeDocument()

describe('usePatientClinicalDocuments', () => {
  beforeEach(() => {
    mockedListClinicalDocuments.mockReset()
    mockedDeleteClinicalDocument.mockReset()
  })

  it('starts in a loading state with no documents and no error', () => {
    mockedListClinicalDocuments.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => usePatientClinicalDocuments(42))

    expect(result.current.isLoading).toBe(true)
    expect(result.current.documents).toEqual([])
    expect(result.current.error).toBeNull()
  })

  it('fetches documents scoped to the given patientId', async () => {
    mockedListClinicalDocuments.mockResolvedValue([sampleDocument])

    const { result } = renderHook(() => usePatientClinicalDocuments(42))

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.documents).toEqual([sampleDocument])
    expect(mockedListClinicalDocuments).toHaveBeenCalledWith(42)
  })

  it('exposes the error message when the initial fetch fails', async () => {
    mockedListClinicalDocuments.mockRejectedValue({
      status: 500,
      message: 'Something went wrong.',
    })

    const { result } = renderHook(() => usePatientClinicalDocuments(42))

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBe('Something went wrong.')
  })

  it('retry() re-fetches and can recover from a previous error', async () => {
    mockedListClinicalDocuments.mockRejectedValueOnce({ status: 500, message: 'Server error.' })
    mockedListClinicalDocuments.mockResolvedValueOnce([sampleDocument])

    const { result } = renderHook(() => usePatientClinicalDocuments(42))

    await waitFor(() => expect(result.current.error).toBe('Server error.'))

    act(() => {
      result.current.retry()
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBeNull()
    expect(result.current.documents).toEqual([sampleDocument])
    expect(mockedListClinicalDocuments).toHaveBeenCalledTimes(2)
  })

  it('re-fetches when patientId changes, so switching patients never shows stale data', async () => {
    mockedListClinicalDocuments.mockResolvedValueOnce([makeDocument({ id: 1, patient_id: 42 })])
    mockedListClinicalDocuments.mockResolvedValueOnce([makeDocument({ id: 2, patient_id: 99 })])

    const { result, rerender } = renderHook(
      ({ patientId }) => usePatientClinicalDocuments(patientId),
      { initialProps: { patientId: 42 } },
    )

    await waitFor(() =>
      expect(result.current.documents).toEqual([expect.objectContaining({ id: 1 })]),
    )

    rerender({ patientId: 99 })

    await waitFor(() =>
      expect(result.current.documents).toEqual([expect.objectContaining({ id: 2 })]),
    )
    expect(mockedListClinicalDocuments).toHaveBeenNthCalledWith(1, 42)
    expect(mockedListClinicalDocuments).toHaveBeenNthCalledWith(2, 99)
  })

  it('removeDocument removes the matching document from local state', async () => {
    mockedListClinicalDocuments.mockResolvedValue([sampleDocument])
    mockedDeleteClinicalDocument.mockResolvedValue(undefined)

    const { result } = renderHook(() => usePatientClinicalDocuments(42))
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.removeDocument(1)
    })

    expect(result.current.documents).toEqual([])
    expect(mockedDeleteClinicalDocument).toHaveBeenCalledWith(42, 1)
  })

  it('removeDocument propagates the error without changing local state', async () => {
    mockedListClinicalDocuments.mockResolvedValue([sampleDocument])
    mockedDeleteClinicalDocument.mockRejectedValue({ status: 500, message: 'Delete failed.' })

    const { result } = renderHook(() => usePatientClinicalDocuments(42))
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await expect(
      act(async () => {
        await result.current.removeDocument(1)
      }),
    ).rejects.toMatchObject({ message: 'Delete failed.' })
    expect(result.current.documents).toEqual([sampleDocument])
  })
})
