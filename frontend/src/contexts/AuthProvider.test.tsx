import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/contexts/AuthProvider'
import { useAuth } from '@/hooks/useAuth'
import { getCurrentUser, loginUser } from '@/api/auth'
import { getStoredToken, setStoredToken } from '@/lib/tokenStorage'
import type { User } from '@/types/api'

vi.mock('@/api/auth')

const mockedLoginUser = vi.mocked(loginUser)
const mockedGetCurrentUser = vi.mocked(getCurrentUser)

// AuthProvider registers a real callback with api/client's module-level
// unauthorizedHandler via setUnauthorizedHandler; captured here so a
// background 401 (the thing the real Axios interceptor would trigger) can
// be simulated directly, without standing up a full mocked HTTP round-trip.
const { unauthorizedHandlerRef } = vi.hoisted(() => ({
  unauthorizedHandlerRef: { current: null as (() => void) | null },
}))

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()

  return {
    ...actual,
    setUnauthorizedHandler: (handler: (() => void) | null) => {
      unauthorizedHandlerRef.current = handler
    },
  }
})

const user: User = {
  id: 1,
  email: 'jane@example.com',
  name: 'Jane',
  username: null,
  created_at: '2026-01-01T00:00:00Z',
}

function Harness() {
  const auth = useAuth()

  return (
    <div>
      <span data-testid="isLoading">{String(auth.isLoading)}</span>
      <span data-testid="isAuthenticated">{String(auth.isAuthenticated)}</span>
      <span data-testid="userName">{auth.user?.name ?? 'none'}</span>
      <span data-testid="sessionExpiredMessage">{auth.sessionExpiredMessage ?? 'none'}</span>
      <button onClick={() => void auth.login('jane@example.com', 'password123')}>Login</button>
      <button onClick={() => auth.logout()}>Logout</button>
      <button onClick={() => auth.clearSessionExpiredMessage()}>Clear expiry message</button>
    </div>
  )
}

function renderAuth() {
  return render(
    <AuthProvider>
      <Harness />
    </AuthProvider>,
  )
}

describe('AuthProvider', () => {
  beforeEach(() => {
    localStorage.clear()
    mockedLoginUser.mockReset()
    mockedGetCurrentUser.mockReset()
    unauthorizedHandlerRef.current = null
  })

  it('starts unauthenticated with no stored token, not loading', () => {
    renderAuth()

    expect(screen.getByTestId('isLoading')).toHaveTextContent('false')
    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('false')
    expect(screen.getByTestId('userName')).toHaveTextContent('none')
  })

  it('restores a session from a stored token, validating it against the backend', async () => {
    setStoredToken('stored-token')
    mockedGetCurrentUser.mockResolvedValue(user)

    renderAuth()

    // Starts in a loading state; the stored token hasn't been validated yet.
    expect(screen.getByTestId('isLoading')).toHaveTextContent('true')

    await waitFor(() => expect(screen.getByTestId('isLoading')).toHaveTextContent('false'))
    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('true')
    expect(screen.getByTestId('userName')).toHaveTextContent('Jane')
  })

  it('clears an invalid stored token instead of trusting it', async () => {
    setStoredToken('expired-token')
    mockedGetCurrentUser.mockRejectedValue({ status: 401, message: 'Invalid token' })

    renderAuth()
    await waitFor(() => expect(screen.getByTestId('isLoading')).toHaveTextContent('false'))

    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('false')
    expect(getStoredToken()).toBeNull()
  })

  it('logs in, persisting the token and fetching the current user', async () => {
    const testUser = userEvent.setup()
    mockedLoginUser.mockResolvedValue({ access_token: 'new-token', token_type: 'bearer' })
    mockedGetCurrentUser.mockResolvedValue(user)

    renderAuth()
    await testUser.click(screen.getByRole('button', { name: 'Login' }))

    await waitFor(() => expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('true'))
    expect(screen.getByTestId('userName')).toHaveTextContent('Jane')
    expect(getStoredToken()).toBe('new-token')
    expect(mockedLoginUser).toHaveBeenCalledWith({
      email: 'jane@example.com',
      password: 'password123',
    })
  })

  it('logs out, clearing user, token, and storage', async () => {
    const testUser = userEvent.setup()
    mockedLoginUser.mockResolvedValue({ access_token: 'new-token', token_type: 'bearer' })
    mockedGetCurrentUser.mockResolvedValue(user)

    renderAuth()
    await testUser.click(screen.getByRole('button', { name: 'Login' }))
    await waitFor(() => expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('true'))

    await testUser.click(screen.getByRole('button', { name: 'Logout' }))

    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('false')
    expect(screen.getByTestId('userName')).toHaveTextContent('none')
    expect(getStoredToken()).toBeNull()
  })

  it('registers a handler for a background 401 that logs out silently and explains why on next login attempt', async () => {
    const testUser = userEvent.setup()
    mockedLoginUser.mockResolvedValue({ access_token: 'new-token', token_type: 'bearer' })
    mockedGetCurrentUser.mockResolvedValue(user)

    renderAuth()
    await testUser.click(screen.getByRole('button', { name: 'Login' }))
    await waitFor(() => expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('true'))

    expect(unauthorizedHandlerRef.current).toBeInstanceOf(Function)

    // Simulates what the Axios response interceptor does on a 401 from an
    // already-authenticated request; the session ended without the user
    // clicking "Log out" themselves.
    act(() => {
      unauthorizedHandlerRef.current?.()
    })

    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('false')
    expect(getStoredToken()).toBeNull()
    expect(screen.getByTestId('sessionExpiredMessage')).toHaveTextContent(
      'Your session has expired. Please log in again.',
    )
  })

  it('clears the session-expired message on demand', async () => {
    const testUser = userEvent.setup()
    mockedLoginUser.mockResolvedValue({ access_token: 'new-token', token_type: 'bearer' })
    mockedGetCurrentUser.mockResolvedValue(user)

    renderAuth()
    await testUser.click(screen.getByRole('button', { name: 'Login' }))
    await waitFor(() => expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('true'))

    act(() => {
      unauthorizedHandlerRef.current?.()
    })
    expect(screen.getByTestId('sessionExpiredMessage')).toHaveTextContent(
      'Your session has expired. Please log in again.',
    )

    await testUser.click(screen.getByRole('button', { name: 'Clear expiry message' }))

    expect(screen.getByTestId('sessionExpiredMessage')).toHaveTextContent('none')
  })
})
