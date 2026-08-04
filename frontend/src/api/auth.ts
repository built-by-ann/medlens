import { apiClient } from '@/api/client'
import type { AuthToken, User } from '@/types/api'

export interface RegisterPayload {
  email: string
  password: string
  username: string
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

export async function getCurrentUser(): Promise<User> {
  const response = await apiClient.get<User>('/users/me')

  return response.data
}

export interface UpdateUserPayload {
  name?: string | null
  email?: string
  username?: string | null
}

export async function updateUser(payload: UpdateUserPayload): Promise<User> {
  const response = await apiClient.patch<User>('/users/me', payload)

  return response.data
}
