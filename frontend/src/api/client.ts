import axios, { AxiosError } from 'axios'
import { env } from '@/lib/env'

export interface ApiError {
  status: number | null
  message: string
  // The raw `detail` value from the backend response, preserved as-is
  // alongside `message` for the rare caller that needs more structure than
  // a single string, e.g. the medication CSV importer's row-level
  // validation errors (`{ message, row_errors }`), which no other endpoint
  // in this app returns. Most callers only ever read `.message`.
  detail?: unknown
}

/**
 * Normalizes backend error responses into a single shape. FastAPI's
 * validation errors return `detail` as a list of field errors rather than a
 * string, so both cases are collapsed into one message here.
 */
export function toApiError(error: AxiosError): ApiError {
  const status = error.response?.status ?? null

  // No response at all: the request never reached a server to produce a
  // `detail` body (offline, DNS/CORS failure, the backend is down, a
  // timeout). Axios's own `error.message` for this case is developer-facing
  // ("Network Error", "timeout of 10000ms exceeded"), not something to show
  // a user, so this is the one case with a fixed, friendly message rather
  // than passing anything from `error` through.
  if (!error.response) {
    return { status, message: 'Unable to reach the server. Check your connection and try again.' }
  }

  const detail = (error.response.data as { detail?: unknown } | undefined)?.detail

  if (typeof detail === 'string') {
    return { status, message: detail, detail }
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (typeof item === 'object' && item && 'msg' in item ? String(item.msg) : null))
      .filter((message): message is string => message !== null)

    if (messages.length > 0) {
      return { status, message: messages.join(', '), detail }
    }
  }

  if (
    detail &&
    typeof detail === 'object' &&
    'message' in detail &&
    typeof detail.message === 'string'
  ) {
    return { status, message: detail.message, detail }
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
