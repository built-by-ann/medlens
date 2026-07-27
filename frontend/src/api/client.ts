import axios, { AxiosError } from 'axios'
import { env } from '@/lib/env'

export interface ApiError {
  status: number | null
  message: string
}

/**
 * Normalizes backend error responses into a single shape. FastAPI's
 * validation errors return `detail` as a list of field errors rather than a
 * string, so both cases are collapsed into one message here.
 */
function toApiError(error: AxiosError): ApiError {
  const status = error.response?.status ?? null
  const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail

  if (typeof detail === 'string') {
    return { status, message: detail }
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (typeof item === 'object' && item && 'msg' in item ? String(item.msg) : null))
      .filter((message): message is string => message !== null)

    if (messages.length > 0) {
      return { status, message: messages.join(', ') }
    }
  }

  return { status, message: error.message || 'An unexpected error occurred.' }
}

export const apiClient = axios.create({
  baseURL: env.apiBaseUrl,
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => Promise.reject(toApiError(error)),
)
