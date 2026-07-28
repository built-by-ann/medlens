import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useRecentAnalyses } from '@/hooks/useRecentAnalyses'
import { listRecentAnalyses } from '@/api/analyses'
import type { AnalysisSummary } from '@/types/api'

vi.mock('@/api/analyses')

const mockedListRecentAnalyses = vi.mocked(listRecentAnalyses)

const sampleAnalysis: AnalysisSummary = {
  id: 1,
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

describe('useRecentAnalyses', () => {
  beforeEach(() => {
    mockedListRecentAnalyses.mockReset()
  })

  it('starts in a loading state with no analyses and no error', () => {
    mockedListRecentAnalyses.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useRecentAnalyses())

    expect(result.current.isLoading).toBe(true)
    expect(result.current.analyses).toEqual([])
    expect(result.current.error).toBeNull()
  })

  it('resolves with the fetched analyses and clears the loading state', async () => {
    mockedListRecentAnalyses.mockResolvedValue([sampleAnalysis])

    const { result } = renderHook(() => useRecentAnalyses())

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.analyses).toEqual([sampleAnalysis])
    expect(result.current.error).toBeNull()
  })

  it('exposes the error message when the request fails', async () => {
    mockedListRecentAnalyses.mockRejectedValue({ status: 500, message: 'Something went wrong.' })

    const { result } = renderHook(() => useRecentAnalyses())

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.error).toBe('Something went wrong.')
    expect(result.current.analyses).toEqual([])
  })

  it('retry() re-fetches and can recover from a previous error', async () => {
    mockedListRecentAnalyses.mockRejectedValueOnce({ status: 500, message: 'Server error.' })
    mockedListRecentAnalyses.mockResolvedValueOnce([sampleAnalysis])

    const { result } = renderHook(() => useRecentAnalyses())

    await waitFor(() => expect(result.current.error).toBe('Server error.'))

    act(() => {
      result.current.retry()
    })

    expect(result.current.isLoading).toBe(true)

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.error).toBeNull()
    expect(result.current.analyses).toEqual([sampleAnalysis])
    expect(mockedListRecentAnalyses).toHaveBeenCalledTimes(2)
  })

  it('passes the given limit through to listRecentAnalyses', () => {
    mockedListRecentAnalyses.mockReturnValue(new Promise(() => {}))

    renderHook(() => useRecentAnalyses(5))

    expect(mockedListRecentAnalyses).toHaveBeenCalledWith(5)
  })
})
