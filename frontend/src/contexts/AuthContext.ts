import { createContext } from 'react'
import type { User } from '@/types/api'

export interface AuthContextValue {
  user: User | null
  isLoading: boolean
  login: (user: User) => void
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)
