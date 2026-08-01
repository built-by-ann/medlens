import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useRecentAnalyses } from '@/hooks/useRecentAnalyses'
import { getRecentAnalyses } from '@/api/analyses'
import type { RecentAnalysis } from '@/types/api'

vi.mock('@/api/analyses')

const mockedGetRecentAnalyses = vi.mocked(getRecentAnalyses)

const sampleAnalysis: RecentAnalysis = {
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
  open_findings: 0,
  provider: 'gemini',
  model_name: 'gemini-2.0-flash',
  patient: { id: 7, first_name: 'Jane', last_name: 'Doe' },
}

describe('useRecentAnalyses', () => {
  beforeEach(() => {
    mockedGetRecentAnalyses.mockReset()
  })

  it('starts in a loading state with no analyses and no error', () => {
    mockedGetRecentAnalyses.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useRecentAnalyses())

    expect(result.current.isLoading).toBe(true)
    expect(result.current.analyses).toEqual([])
    expect(result.current.error).toBeNull()
  })

  it('resolves with the fetched analyses and clears the loading state', async () => {
    mockedGetRecentAnalyses.mockResolvedValue([sampleAnalysis])

    const { result } = renderHook(() => useRecentAnalyses())

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.analyses).toEqual([sampleAnalysis])
    expect(result.current.error).toBeNull()
  })

  it('defaults to a limit of 3', () => {
    mockedGetRecentAnalyses.mockReturnValue(new Promise(() => {}))

    renderHook(() => useRecentAnalyses())

    expect(mockedGetRecentAnalyses).toHaveBeenCalledWith(3)
  })

  it('passes a custom limit through', () => {
    mockedGetRecentAnalyses.mockReturnValue(new Promise(() => {}))

    renderHook(() => useRecentAnalyses(5))

    expect(mockedGetRecentAnalyses).toHaveBeenCalledWith(5)
  })

  it('exposes the error message when the request fails', async () => {
    mockedGetRecentAnalyses.mockRejectedValue({ status: 500, message: 'Something went wrong.' })

    const { result } = renderHook(() => useRecentAnalyses())

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.error).toBe('Something went wrong.')
    expect(result.current.analyses).toEqual([])
  })

  it('retry() re-fetches and can recover from a previous error', async () => {
    mockedGetRecentAnalyses.mockRejectedValueOnce({ status: 500, message: 'Server error.' })
    mockedGetRecentAnalyses.mockResolvedValueOnce([sampleAnalysis])

    const { result } = renderHook(() => useRecentAnalyses())

    await waitFor(() => expect(result.current.error).toBe('Server error.'))

    act(() => {
      result.current.retry()
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBeNull()
    expect(result.current.analyses).toEqual([sampleAnalysis])
    expect(mockedGetRecentAnalyses).toHaveBeenCalledTimes(2)
  })
})
