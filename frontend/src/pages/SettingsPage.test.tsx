import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SettingsPage } from '@/pages/SettingsPage'
import { ThemeProvider } from '@/contexts/ThemeProvider'
import { useAuth } from '@/hooks/useAuth'

vi.mock('@/hooks/useAuth')

const mockedUseAuth = vi.mocked(useAuth)

function renderSettings() {
  return render(
    <ThemeProvider>
      <SettingsPage />
    </ThemeProvider>,
  )
}

describe('SettingsPage', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    mockedUseAuth.mockReturnValue({
      user: {
        id: 1,
        email: 'a@example.com',
        name: 'Jane Doe',
        username: null,
        created_at: '2026-01-01T00:00:00Z',
      },
      token: 'token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      setUser: vi.fn(),
      sessionExpiredMessage: null,
      clearSessionExpiredMessage: vi.fn(),
    })
  })

  it('shows the page title', () => {
    renderSettings()

    expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument()
  })

  it('renders Profile, Appearance, Accessibility, and About sections', () => {
    renderSettings()

    expect(screen.getByRole('heading', { name: 'Profile' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Appearance' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Accessibility' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'About' })).toBeInTheDocument()
  })
})
