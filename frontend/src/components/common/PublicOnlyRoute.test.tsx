import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PublicOnlyRoute } from '@/components/common/PublicOnlyRoute'
import { useAuth } from '@/hooks/useAuth'

vi.mock('@/hooks/useAuth')

const mockedUseAuth = vi.mocked(useAuth)

function renderPublicOnly(initialEntry = '/login') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/dashboard" element={<div>Dashboard stub</div>} />
        <Route
          path="/login"
          element={
            <PublicOnlyRoute>
              <div>Login form</div>
            </PublicOnlyRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('PublicOnlyRoute', () => {
  beforeEach(() => {
    mockedUseAuth.mockReset()
  })

  it('shows a loading state and renders neither the page nor a redirect while auth is initializing', () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: true,
      login: vi.fn(),
      logout: vi.fn(),
      sessionExpiredMessage: null,
      clearSessionExpiredMessage: vi.fn(),
    })

    renderPublicOnly()

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.queryByText('Login form')).not.toBeInTheDocument()
    expect(screen.queryByText('Dashboard stub')).not.toBeInTheDocument()
  })

  it('redirects an already-authenticated user to the dashboard instead of showing the page', () => {
    mockedUseAuth.mockReturnValue({
      user: { id: 1, email: 'a@example.com', name: 'A', created_at: '2026-01-01T00:00:00Z' },
      token: 'token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      sessionExpiredMessage: null,
      clearSessionExpiredMessage: vi.fn(),
    })

    renderPublicOnly()

    expect(screen.getByText('Dashboard stub')).toBeInTheDocument()
    expect(screen.queryByText('Login form')).not.toBeInTheDocument()
  })

  it('renders the page for an unauthenticated visitor', () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      sessionExpiredMessage: null,
      clearSessionExpiredMessage: vi.fn(),
    })

    renderPublicOnly()

    expect(screen.getByText('Login form')).toBeInTheDocument()
    expect(screen.queryByText('Dashboard stub')).not.toBeInTheDocument()
  })
})
