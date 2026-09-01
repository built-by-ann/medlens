import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { User } from '@/types/api'
import { AuthContext, type AuthContextValue } from '@/contexts/AuthContext'
import { getCurrentUser, loginUser } from '@/api/auth'
import { setAuthToken, setUnauthorizedHandler } from '@/api/client'
import { clearStoredToken, getStoredToken, setStoredToken } from '@/lib/tokenStorage'

interface AuthProviderProps {
  children: ReactNode
}

/**
 * Owns authentication state: the current user, the access token, and
 * whether the initial session restore is still in progress. Session
 * persistence (localStorage) and the API client's request/response
 * interceptors are separate modules; this provider is what keeps them in
 * sync with React state, rather than either of them reading storage or
 * context directly.
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [sessionExpiredMessage, setSessionExpiredMessage] = useState<string | null>(null)
  // When there is no stored token there is nothing to restore, so this can
  // be computed synchronously up front rather than always starting at true
  // and flipping to false in an effect a moment later.
  const [isLoading, setIsLoading] = useState(() => getStoredToken() !== null)

  // Restore the session on load. A stored token is applied to the API
  // client immediately so it is not lost if this component re-renders
  // before the GET /users/me call resolves, then validated against the
  // backend; an invalid or expired token is cleared rather than trusted.
  useEffect(() => {
    const storedToken = getStoredToken()

    if (!storedToken) {
      return
    }

    // StrictMode double-invokes this effect in dev, firing two concurrent
    // getCurrentUser() calls. Without this guard, a stale call's rejection
    // (e.g. a transient blip) would clear the token even after the other,
    // newer call already succeeded and restored the session, leaving
    // `user` set (so the UI looks logged in) while apiClient's token is
    // null (so every subsequent request 401s with no Authorization header
    // at all). ignore makes only the effect run's own outcome apply.
    let ignore = false

    setAuthToken(storedToken)

    getCurrentUser()
      .then((currentUser) => {
        if (ignore) return
        setToken(storedToken)
        setUser(currentUser)
      })
      .catch(() => {
        if (ignore) return
        clearStoredToken()
        setAuthToken(null)
      })
      .finally(() => {
        if (!ignore) setIsLoading(false)
      })

    return () => {
      ignore = true
    }
  }, [])

  // A 401 on a request that was sent with a token means the session itself
  // is no longer valid (expired or revoked), not that this one request had
  // bad input, so it is treated the same as an explicit logout.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearStoredToken()
      setAuthToken(null)
      setToken(null)
      setUser(null)
      setSessionExpiredMessage('Your session has expired. Please log in again.')
    })

    return () => setUnauthorizedHandler(null)
  }, [])

  const login = useCallback(async (email: string, password: string): Promise<void> => {
    const authToken = await loginUser({ email, password })

    setStoredToken(authToken.access_token)
    setAuthToken(authToken.access_token)

    const currentUser = await getCurrentUser()

    setToken(authToken.access_token)
    setUser(currentUser)
  }, [])

  const logout = useCallback((): void => {
    clearStoredToken()
    setAuthToken(null)
    setToken(null)
    setUser(null)
  }, [])

  const clearSessionExpiredMessage = useCallback(() => setSessionExpiredMessage(null), [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isAuthenticated: user !== null,
      isLoading,
      login,
      logout,
      setUser,
      sessionExpiredMessage,
      clearSessionExpiredMessage,
    }),
    [user, token, isLoading, login, logout, sessionExpiredMessage, clearSessionExpiredMessage],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
