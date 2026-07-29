import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAnalysisPolling } from '@/hooks/useAnalysisPolling'
import { getAnalysisDetail } from '@/api/analyses'
import type { AnalysisDetail } from '@/types/api'

vi.mock('@/api/analyses', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/analyses')>()

  return {
    ...actual,
    getAnalysisDetail: vi.fn(),
  }
})

const mockedGetAnalysisDetail = vi.mocked(getAnalysisDetail)

function makeAnalysis(overrides: Partial<AnalysisDetail> = {}): AnalysisDetail {
  return {
    id: 7,
    patient_id: 42,
    status: 'processing',
    provider: null,
    model_name: null,
    summary: null,
    started_at: null,
    completed_at: null,
    error_message: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    medication_discrepancies: [],
    ...overrides,
  }
}

async function flush() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0)
  })
}

describe('useAnalysisPolling', () => {
  beforeEach(() => {
    mockedGetAnalysisDetail.mockReset()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('stays idle and makes no request while analysisId is null', async () => {
    const { result } = renderHook(() => useAnalysisPolling(42, null))

    await flush()

    expect(mockedGetAnalysisDetail).not.toHaveBeenCalled()
    expect(result.current.analysis).toBeNull()
    expect(result.current.error).toBeNull()
  })

  it('fetches immediately once an analysisId is provided', async () => {
    mockedGetAnalysisDetail.mockResolvedValue(makeAnalysis({ status: 'completed' }))

    const { result } = renderHook(() => useAnalysisPolling(42, 7))
    await flush()

    expect(mockedGetAnalysisDetail).toHaveBeenCalledWith(42, 7)
    expect(result.current.analysis?.status).toBe('completed')
  })

  it('keeps polling at the given interval while status is pending or processing, then stops once completed', async () => {
    mockedGetAnalysisDetail
      .mockResolvedValueOnce(makeAnalysis({ status: 'pending' }))
      .mockResolvedValueOnce(makeAnalysis({ status: 'processing' }))
      .mockResolvedValueOnce(makeAnalysis({ status: 'completed' }))

    const { result } = renderHook(() => useAnalysisPolling(42, 7, 1000))

    await flush()
    expect(result.current.analysis?.status).toBe('pending')
    expect(mockedGetAnalysisDetail).toHaveBeenCalledTimes(1)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(result.current.analysis?.status).toBe('processing')
    expect(mockedGetAnalysisDetail).toHaveBeenCalledTimes(2)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(result.current.analysis?.status).toBe('completed')
    expect(mockedGetAnalysisDetail).toHaveBeenCalledTimes(3)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(mockedGetAnalysisDetail).toHaveBeenCalledTimes(3)
  })

  it('stops polling once status is failed', async () => {
    mockedGetAnalysisDetail.mockResolvedValue(
      makeAnalysis({ status: 'failed', error_message: 'The AI provider returned an error.' }),
    )

    const { result } = renderHook(() => useAnalysisPolling(42, 7, 1000))
    await flush()

    expect(result.current.analysis?.status).toBe('failed')

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(mockedGetAnalysisDetail).toHaveBeenCalledTimes(1)
  })

  it('exposes the error message when the request fails', async () => {
    mockedGetAnalysisDetail.mockRejectedValue({ status: 500, message: 'Server error.' })

    const { result } = renderHook(() => useAnalysisPolling(42, 7))
    await flush()

    expect(result.current.error).toBe('Server error.')
    expect(result.current.analysis).toBeNull()
  })

  it('restarts polling when analysisId changes', async () => {
    mockedGetAnalysisDetail.mockResolvedValueOnce(makeAnalysis({ id: 7, status: 'completed' }))
    mockedGetAnalysisDetail.mockResolvedValueOnce(makeAnalysis({ id: 8, status: 'processing' }))

    const { result, rerender } = renderHook(
      ({ analysisId }) => useAnalysisPolling(42, analysisId, 1000),
      { initialProps: { analysisId: 7 as number | null } },
    )
    await flush()
    expect(result.current.analysis?.id).toBe(7)

    rerender({ analysisId: 8 })
    await flush()

    expect(result.current.analysis?.id).toBe(8)
    expect(mockedGetAnalysisDetail).toHaveBeenNthCalledWith(1, 42, 7)
    expect(mockedGetAnalysisDetail).toHaveBeenNthCalledWith(2, 42, 8)
  })
})
