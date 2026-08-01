import { renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import { useTheme } from '@/hooks/useTheme'
import { ThemeContext, type ThemeContextValue } from '@/contexts/ThemeContext'

const value: ThemeContextValue = {
  palette: 'default',
  modePreference: 'system',
  resolvedMode: 'light',
  resolvedTheme: 'default-light',
  setPalette: () => {},
  setModePreference: () => {},
}

describe('useTheme', () => {
  it('throws when used outside a ThemeProvider', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => renderHook(() => useTheme())).toThrow(
      'useTheme must be used within a ThemeProvider',
    )
    consoleError.mockRestore()
  })

  it('returns the current context value when used inside a ThemeProvider', () => {
    function wrapper({ children }: { children: ReactNode }) {
      return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
    }
    const { result } = renderHook(() => useTheme(), { wrapper })
    expect(result.current).toBe(value)
  })
})
