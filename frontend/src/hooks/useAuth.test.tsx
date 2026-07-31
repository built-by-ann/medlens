import { renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { AuthContext, type AuthContextValue } from '@/contexts/AuthContext'

const value: AuthContextValue = {
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: false,
  login: async () => {},
  logout: () => {},
  sessionExpiredMessage: null,
  clearSessionExpiredMessage: () => {},
}

describe('useAuth', () => {
  it('throws when used outside an AuthProvider', () => {
    // Suppress the expected React error-boundary console noise this
    // triggers, so a legitimate failure elsewhere isn't lost in it.
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(() => renderHook(() => useAuth())).toThrow('useAuth must be used within an AuthProvider')

    consoleError.mockRestore()
  })

  it('returns the current context value when used inside an AuthProvider', () => {
    function wrapper({ children }: { children: ReactNode }) {
      return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
    }

    const { result } = renderHook(() => useAuth(), { wrapper })

    expect(result.current).toBe(value)
  })
})
