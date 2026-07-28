import { useMemo, useState, type ReactNode } from 'react'
import type { User } from '@/types/api'
import { AuthContext, type AuthContextValue } from '@/contexts/AuthContext'

interface AuthProviderProps {
  children: ReactNode
}

/**
 * Holds authentication state only. Session restoration, real login/signup
 * requests, and token persistence are deferred to the issues that implement
 * those flows; this provider exists so routing and the API layer have a
 * stable shape to build against.
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading] = useState(false)

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      login: setUser,
      logout: () => setUser(null),
    }),
    [user, isLoading],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
