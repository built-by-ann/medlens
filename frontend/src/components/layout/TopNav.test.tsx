import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { TopNav } from '@/components/layout/TopNav'
import { useAuth } from '@/hooks/useAuth'
import type { User } from '@/types/api'

vi.mock('@/hooks/useAuth')

const mockedUseAuth = vi.mocked(useAuth)

const user: User = {
  id: 1,
  email: 'jane@example.com',
  name: 'Jane',
  username: null,
  created_at: '2026-01-01T00:00:00Z',
}

function renderNav(initialEntry = '/dashboard') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <TopNav />
    </MemoryRouter>,
  )
}

describe('TopNav', () => {
  it('shows Dashboard and Patients links, and marks the current route as active', () => {
    mockedUseAuth.mockReturnValue({
      user,
      token: 'token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      setUser: vi.fn(),
      sessionExpiredMessage: null,
      clearSessionExpiredMessage: vi.fn(),
    })

    renderNav('/patients')

    const dashboardLink = screen.getByRole('link', { name: 'Dashboard' })
    const patientsLink = screen.getByRole('link', { name: 'Patients' })

    expect(dashboardLink).toHaveAttribute('href', '/dashboard')
    expect(patientsLink).toHaveAttribute('href', '/patients')
    expect(patientsLink).toHaveAttribute('aria-current', 'page')
    expect(dashboardLink).not.toHaveAttribute('aria-current')
  })

  it('shows a Settings link', () => {
    mockedUseAuth.mockReturnValue({
      user,
      token: 'token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      setUser: vi.fn(),
      sessionExpiredMessage: null,
      clearSessionExpiredMessage: vi.fn(),
    })

    renderNav()

    expect(screen.getByRole('link', { name: 'Settings' })).toHaveAttribute('href', '/settings')
  })

  it('shows a Log out button for an authenticated user, which calls logout when clicked', async () => {
    const logout = vi.fn()
    const testUser = userEvent.setup()
    mockedUseAuth.mockReturnValue({
      user,
      token: 'token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout,
      setUser: vi.fn(),
      sessionExpiredMessage: null,
      clearSessionExpiredMessage: vi.fn(),
    })

    renderNav()
    await testUser.click(screen.getByRole('button', { name: 'Log out' }))

    expect(logout).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('link', { name: 'Log in' })).not.toBeInTheDocument()
  })

  it('shows a Log in link instead of Log out when there is no authenticated user', () => {
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

    renderNav()

    expect(screen.getByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login')
    expect(screen.queryByRole('button', { name: 'Log out' })).not.toBeInTheDocument()
  })
})
