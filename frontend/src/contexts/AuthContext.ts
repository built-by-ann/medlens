import { createContext } from 'react'
import type { User } from '@/types/api'

export interface AuthContextValue {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  // Set when the session was ended for the user rather than by their own
  // choice (a 401 on an already-authenticated request - the token expired
  // or was revoked). Previously this was a fully silent logout with no
  // explanation; LoginPage reads this once, shows it, then clears it, so
  // it's a one-time message rather than something that could reappear.
  sessionExpiredMessage: string | null
  clearSessionExpiredMessage: () => void
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)
