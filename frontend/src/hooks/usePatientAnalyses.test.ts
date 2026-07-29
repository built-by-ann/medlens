import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { usePatientAnalyses } from '@/hooks/usePatientAnalyses'
import { listAnalyses } from '@/api/analyses'
import type { AnalysisSummary } from '@/types/api'

vi.mock('@/api/analyses')

const mockedListAnalyses = vi.mocked(listAnalyses)

const sampleAnalysis: AnalysisSummary = {
  id: 1,
  patient_id: 7,
  status: 'completed',
  created_at: '2026-01-01T00:00:00Z',
  completed_at: '2026-01-01T00:05:00Z',
  error_message: null,
  summary: 'Found 1 finding.',
  document_count: 2,
  total_findings: 1,
  high_severity_findings: 0,
  medium_severity_findings: 1,
  low_severity_findings: 0,
  provider: 'gemini',
  model_name: 'gemini-2.0-flash',
}

describe('usePatientAnalyses', () => {
  beforeEach(() => {
    mockedListAnalyses.mockReset()
  })

  it('starts in a loading state with no analyses and no error', () => {
    mockedListAnalyses.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => usePatientAnalyses(7))

    expect(result.current.isLoading).toBe(true)
    expect(result.current.analyses).toEqual([])
    expect(result.current.error).toBeNull()
  })

  it('resolves with the fetched analyses and clears the loading state', async () => {
    mockedListAnalyses.mockResolvedValue([sampleAnalysis])

    const { result } = renderHook(() => usePatientAnalyses(7))

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.analyses).toEqual([sampleAnalysis])
    expect(result.current.error).toBeNull()
  })

  it('exposes the error message when the request fails', async () => {
    mockedListAnalyses.mockRejectedValue({ status: 500, message: 'Something went wrong.' })

    const { result } = renderHook(() => usePatientAnalyses(7))

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.error).toBe('Something went wrong.')
    expect(result.current.analyses).toEqual([])
  })

  it('retry() re-fetches and can recover from a previous error', async () => {
    mockedListAnalyses.mockRejectedValueOnce({ status: 500, message: 'Server error.' })
    mockedListAnalyses.mockResolvedValueOnce([sampleAnalysis])

    const { result } = renderHook(() => usePatientAnalyses(7))

    await waitFor(() => expect(result.current.error).toBe('Server error.'))

    act(() => {
      result.current.retry()
    })

    expect(result.current.isLoading).toBe(true)

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.error).toBeNull()
    expect(result.current.analyses).toEqual([sampleAnalysis])
    expect(mockedListAnalyses).toHaveBeenCalledTimes(2)
  })

  it('passes the given patientId and limit through to listAnalyses', () => {
    mockedListAnalyses.mockReturnValue(new Promise(() => {}))

    renderHook(() => usePatientAnalyses(7, 5))

    expect(mockedListAnalyses).toHaveBeenCalledWith(7, 5)
  })

  it('re-fetches when patientId changes, scoping strictly to one patient at a time', async () => {
    mockedListAnalyses.mockResolvedValue([sampleAnalysis])

    const { rerender } = renderHook(({ patientId }) => usePatientAnalyses(patientId), {
      initialProps: { patientId: 7 },
    })

    await waitFor(() => expect(mockedListAnalyses).toHaveBeenCalledWith(7, 10))

    rerender({ patientId: 8 })

    await waitFor(() => expect(mockedListAnalyses).toHaveBeenCalledWith(8, 10))
  })
})
