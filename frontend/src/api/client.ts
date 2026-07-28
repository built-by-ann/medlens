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

// The current token is held here, in the API layer, rather than read from
// AuthContext directly (interceptors run outside React and have no access
// to context). AuthContext is still the single owner of the token's value;
// it just calls setAuthToken() whenever that value changes (login, logout,
// session restore), so this module never reads or writes storage itself.
let currentToken: string | null = null

export function setAuthToken(token: string | null): void {
  currentToken = token
}

apiClient.interceptors.request.use((config) => {
  if (currentToken) {
    config.headers.Authorization = `Bearer ${currentToken}`
  }

  return config
})

// Registered by AuthContext so that a 401 on a request that was actually
// sent with a token (meaning the session itself is no longer valid, not
// just "these credentials were wrong") clears authentication state. This is
// intentionally the only thing it does: it never redirects or retries, so
// there is no risk of a loop, and once state is cleared no further request
// carries a token, so a stale token cannot keep re-triggering this handler.
let unauthorizedHandler: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler
}

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const hadAuthHeader = Boolean(error.config?.headers?.Authorization)

    if (error.response?.status === 401 && hadAuthHeader) {
      unauthorizedHandler?.()
    }

    return Promise.reject(toApiError(error))
  },
)
