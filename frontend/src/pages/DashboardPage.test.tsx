import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DashboardPage } from '@/pages/DashboardPage'
import { useAuth } from '@/hooks/useAuth'

vi.mock('@/hooks/useAuth')

const mockedUseAuth = vi.mocked(useAuth)

function renderDashboard() {
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <DashboardPage />
    </MemoryRouter>,
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    mockedUseAuth.mockReturnValue({
      user: { id: 1, email: 'a@example.com', name: 'Jane', created_at: '2026-01-01T00:00:00Z' },
      token: 'token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
    })
  })

  it('shows a welcome header and a link to the patients list', () => {
    renderDashboard()

    expect(screen.getByRole('heading', { name: /Welcome back, Jane/ })).toBeInTheDocument()
    const patientsLink = screen.getByRole('link', { name: 'View patients' })
    expect(patientsLink).toHaveAttribute('href', '/patients')
  })

  it('falls back to a generic welcome message when the user has no name', () => {
    mockedUseAuth.mockReturnValue({
      user: { id: 1, email: 'a@example.com', name: null, created_at: '2026-01-01T00:00:00Z' },
      token: 'token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
    })

    renderDashboard()

    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })
})
