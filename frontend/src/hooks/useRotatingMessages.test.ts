import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useRotatingMessages } from '@/hooks/useRotatingMessages'

describe('useRotatingMessages', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts with the first message', () => {
    const { result } = renderHook(() => useRotatingMessages(['a', 'b', 'c'], 1000))

    expect(result.current).toBe('a')
  })

  it('advances to the next message after each interval, wrapping back to the start', () => {
    const { result } = renderHook(() => useRotatingMessages(['a', 'b', 'c'], 1000))

    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(result.current).toBe('b')

    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(result.current).toBe('c')

    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(result.current).toBe('a')
  })

  it('does not rotate when there is only one message', () => {
    const { result } = renderHook(() => useRotatingMessages(['only'], 1000))

    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(result.current).toBe('only')
  })
})
