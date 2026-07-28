import { apiClient } from '@/api/client'
import type { AuthToken, User } from '@/types/api'

export interface RegisterPayload {
  email: string
  password: string
  name?: string
}

export async function registerUser(payload: RegisterPayload): Promise<User> {
  const response = await apiClient.post<User>('/auth/register', payload)

  return response.data
}

export interface LoginPayload {
  email: string
  password: string
}

export async function loginUser(payload: LoginPayload): Promise<AuthToken> {
  const response = await apiClient.post<AuthToken>('/auth/login', payload)

  return response.data
}
