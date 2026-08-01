import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation, type Location } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ProtectedRoute } from '@/components/common/ProtectedRoute'
import { useAuth } from '@/hooks/useAuth'

vi.mock('@/hooks/useAuth')

const mockedUseAuth = vi.mocked(useAuth)

interface LocationState {
  from?: Location
}

function LoginStub() {
  const location = useLocation()
  const state = location.state as LocationState | null

  return <div>Login page (from: {state?.from?.pathname ?? 'none'})</div>
}

function renderProtected(initialEntry = '/dashboard') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/login" element={<LoginStub />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <div>Protected content</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    mockedUseAuth.mockReset()
  })

  it('shows a loading state and renders neither children nor a redirect while auth is initializing', () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: true,
      login: vi.fn(),
      logout: vi.fn(),
      setUser: vi.fn(),
      sessionExpiredMessage: null,
      clearSessionExpiredMessage: vi.fn(),
    })

    renderProtected()

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.queryByText('Protected content')).not.toBeInTheDocument()
    expect(screen.queryByText(/Login page/)).not.toBeInTheDocument()
  })

  it('redirects unauthenticated users to /login, preserving the attempted location', () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      setUser: vi.fn(),
      sessionExpiredMessage: null,
      clearSessionExpiredMessage: vi.fn(),
    })

    renderProtected('/dashboard')

    expect(screen.getByText('Login page (from: /dashboard)')).toBeInTheDocument()
    expect(screen.queryByText('Protected content')).not.toBeInTheDocument()
  })

  it('renders children for an authenticated user', () => {
    mockedUseAuth.mockReturnValue({
      user: { id: 1, email: 'a@example.com', name: 'A', created_at: '2026-01-01T00:00:00Z' },
      token: 'token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      setUser: vi.fn(),
      sessionExpiredMessage: null,
      clearSessionExpiredMessage: vi.fn(),
    })

    renderProtected()

    expect(screen.getByText('Protected content')).toBeInTheDocument()
    expect(screen.queryByText(/Login page/)).not.toBeInTheDocument()
  })
})
