import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAnalysisDetail } from '@/hooks/useAnalysisDetail'
import { getAnalysisDetail } from '@/api/analyses'
import type { AnalysisDetail, MedicationDiscrepancy } from '@/types/api'

vi.mock('@/api/analyses', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/analyses')>()

  return {
    ...actual,
    getAnalysisDetail: vi.fn(),
  }
})

const mockedGetAnalysisDetail = vi.mocked(getAnalysisDetail)

const sampleAnalysis: AnalysisDetail = {
  id: 7,
  patient_id: 42,
  status: 'completed',
  provider: 'gemini',
  model_name: 'gemini-2.0-flash',
  summary: 'Reconciliation completed with 1 finding.',
  started_at: '2026-01-01T12:00:00Z',
  completed_at: '2026-01-01T12:05:00Z',
  error_message: null,
  created_at: '2026-01-01T11:59:00Z',
  updated_at: '2026-01-01T12:05:00Z',
  document_count: 1,
  medication_mentions: [],
  possible_inconsistencies: [],
  medication_discrepancies: [],
}

describe('useAnalysisDetail', () => {
  beforeEach(() => {
    mockedGetAnalysisDetail.mockReset()
  })

  it('starts in a loading state with no analysis and no error', () => {
    mockedGetAnalysisDetail.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useAnalysisDetail(42, 7))

    expect(result.current.isLoading).toBe(true)
    expect(result.current.analysis).toBeNull()
    expect(result.current.error).toBeNull()
  })

  it('fetches the analysis scoped to patientId and analysisId', async () => {
    mockedGetAnalysisDetail.mockResolvedValue(sampleAnalysis)

    const { result } = renderHook(() => useAnalysisDetail(42, 7))

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.analysis).toEqual(sampleAnalysis)
    expect(mockedGetAnalysisDetail).toHaveBeenCalledWith(42, 7)
  })

  it('exposes the error message when the fetch fails', async () => {
    mockedGetAnalysisDetail.mockRejectedValue({ status: 404, message: 'Analysis not found' })

    const { result } = renderHook(() => useAnalysisDetail(42, 7))

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBe('Analysis not found')
    expect(result.current.analysis).toBeNull()
  })

  it('retry() re-fetches and can recover from a previous error', async () => {
    mockedGetAnalysisDetail.mockRejectedValueOnce({ status: 500, message: 'Server error.' })
    mockedGetAnalysisDetail.mockResolvedValueOnce(sampleAnalysis)

    const { result } = renderHook(() => useAnalysisDetail(42, 7))

    await waitFor(() => expect(result.current.error).toBe('Server error.'))

    act(() => {
      result.current.retry()
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBeNull()
    expect(result.current.analysis).toEqual(sampleAnalysis)
    expect(mockedGetAnalysisDetail).toHaveBeenCalledTimes(2)
  })

  it('re-fetches when analysisId changes', async () => {
    mockedGetAnalysisDetail.mockResolvedValueOnce(sampleAnalysis)
    mockedGetAnalysisDetail.mockResolvedValueOnce({ ...sampleAnalysis, id: 8 })

    const { result, rerender } = renderHook(({ analysisId }) => useAnalysisDetail(42, analysisId), {
      initialProps: { analysisId: 7 },
    })

    await waitFor(() => expect(result.current.analysis?.id).toBe(7))

    rerender({ analysisId: 8 })

    await waitFor(() => expect(result.current.analysis?.id).toBe(8))
    expect(mockedGetAnalysisDetail).toHaveBeenNthCalledWith(1, 42, 7)
    expect(mockedGetAnalysisDetail).toHaveBeenNthCalledWith(2, 42, 8)
  })

  describe('replaceDiscrepancy', () => {
    function makeDiscrepancy(
      overrides: Partial<MedicationDiscrepancy> = {},
    ): MedicationDiscrepancy {
      return {
        id: 1,
        analysis_id: 7,
        medication_id: null,
        medication_mention_id: 9,
        discrepancy_type: 'missing_from_medication_list',
        severity: 'high',
        title: 'Lisinopril not found in medication list',
        ai_explanation: null,
        recommendation: null,
        expected_value: null,
        observed_value: 'Lisinopril',
        resolution_status: 'open',
        resolution_action: null,
        resolved_at: null,
        resolution_note: null,
        resolved_by: null,
        created_at: '2026-01-01T12:01:00Z',
        updated_at: null,
        medication: null,
        medication_mention: null,
        ...overrides,
      }
    }

    it('splices the updated discrepancy into medication_discrepancies in place', async () => {
      const original = makeDiscrepancy()
      mockedGetAnalysisDetail.mockResolvedValue({
        ...sampleAnalysis,
        medication_discrepancies: [original],
      })

      const { result } = renderHook(() => useAnalysisDetail(42, 7))
      await waitFor(() => expect(result.current.isLoading).toBe(false))

      const resolved = makeDiscrepancy({
        resolution_status: 'resolved',
        resolution_action: 'add_medication',
        resolved_at: '2026-01-02T09:00:00Z',
        medication_id: 55,
      })

      act(() => {
        result.current.replaceDiscrepancy(resolved)
      })

      expect(result.current.analysis?.medication_discrepancies).toEqual([resolved])
    })

    it('only replaces the matching discrepancy, leaving others untouched', async () => {
      const first = makeDiscrepancy({ id: 1 })
      const second = makeDiscrepancy({ id: 2, discrepancy_type: 'dose_conflict' })
      mockedGetAnalysisDetail.mockResolvedValue({
        ...sampleAnalysis,
        medication_discrepancies: [first, second],
      })

      const { result } = renderHook(() => useAnalysisDetail(42, 7))
      await waitFor(() => expect(result.current.isLoading).toBe(false))

      const resolvedSecond = makeDiscrepancy({ id: 2, resolution_status: 'dismissed' })

      act(() => {
        result.current.replaceDiscrepancy(resolvedSecond)
      })

      expect(result.current.analysis?.medication_discrepancies).toEqual([first, resolvedSecond])
    })

    it('does nothing if the analysis has not loaded yet', () => {
      mockedGetAnalysisDetail.mockReturnValue(new Promise(() => {}))

      const { result } = renderHook(() => useAnalysisDetail(42, 7))

      expect(() => {
        act(() => {
          result.current.replaceDiscrepancy(makeDiscrepancy())
        })
      }).not.toThrow()
      expect(result.current.analysis).toBeNull()
    })
  })
})
