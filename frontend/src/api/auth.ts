import { apiClient } from '@/api/client'
import type { User } from '@/types/api'

export interface RegisterPayload {
  email: string
  password: string
  name?: string
}

export async function registerUser(payload: RegisterPayload): Promise<User> {
  const response = await apiClient.post<User>('/auth/register', payload)

  return response.data
}
