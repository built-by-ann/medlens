import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ProfileSettings } from '@/components/settings/ProfileSettings'
import { useAuth } from '@/hooks/useAuth'
import { updateUser } from '@/api/auth'
import type { User } from '@/types/api'

vi.mock('@/hooks/useAuth')

vi.mock('@/api/auth', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/auth')>()

  return {
    ...actual,
    updateUser: vi.fn(),
  }
})

const mockedUseAuth = vi.mocked(useAuth)
const mockedUpdateUser = vi.mocked(updateUser)

const baseUser: User = {
  id: 1,
  email: 'ann@example.com',
  name: 'Ann Mathew',
  username: null,
  created_at: '2026-01-01T00:00:00Z',
}

function mockAuth(user: User | null, setUser = vi.fn()) {
  mockedUseAuth.mockReturnValue({
    user,
    token: 'token',
    isAuthenticated: user !== null,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    setUser,
    sessionExpiredMessage: null,
    clearSessionExpiredMessage: vi.fn(),
  })
}

describe('ProfileSettings', () => {
  beforeEach(() => {
    mockedUpdateUser.mockReset()
  })

  it('pre-fills first name, last name, username, and email from the current user', () => {
    mockAuth({ ...baseUser, username: 'annm' })
    render(<ProfileSettings />)

    expect(screen.getByLabelText('First Name')).toHaveValue('Ann')
    expect(screen.getByLabelText('Last Name')).toHaveValue('Mathew')
    expect(screen.getByLabelText('Username')).toHaveValue('annm')
    expect(screen.getByLabelText('Email Address')).toHaveValue('ann@example.com')
  })

  it('pre-fills an empty username for an account that has never set one', () => {
    mockAuth(baseUser)
    render(<ProfileSettings />)

    expect(screen.getByLabelText('Username')).toHaveValue('')
    expect(screen.getByLabelText('Username')).not.toBeDisabled()
  })

  it('shows validation errors and does not submit when a required field is cleared', async () => {
    mockAuth(baseUser)
    const user = userEvent.setup()
    render(<ProfileSettings />)

    await user.clear(screen.getByLabelText('First Name'))
    await user.click(screen.getByRole('button', { name: 'Save Changes' }))

    expect(await screen.findByText('First name is required.')).toBeInTheDocument()
    expect(mockedUpdateUser).not.toHaveBeenCalled()
  })

  it('rejects an invalid email address', async () => {
    mockAuth(baseUser)
    const user = userEvent.setup()
    render(<ProfileSettings />)

    await user.clear(screen.getByLabelText('Email Address'))
    await user.type(screen.getByLabelText('Email Address'), 'not-an-email')
    await user.click(screen.getByRole('button', { name: 'Save Changes' }))

    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument()
    expect(mockedUpdateUser).not.toHaveBeenCalled()
  })

  it('joins first and last name back together and saves, updating shared auth state', async () => {
    const setUser = vi.fn()
    mockAuth(baseUser, setUser)
    const updated: User = { ...baseUser, name: 'Ann Marie Mathew' }
    mockedUpdateUser.mockResolvedValue(updated)
    const user = userEvent.setup()
    render(<ProfileSettings />)

    await user.clear(screen.getByLabelText('Last Name'))
    await user.type(screen.getByLabelText('Last Name'), 'Marie Mathew')
    await user.click(screen.getByRole('button', { name: 'Save Changes' }))

    expect(await screen.findByText('Profile updated.')).toBeInTheDocument()
    expect(mockedUpdateUser).toHaveBeenCalledWith({
      name: 'Ann Marie Mathew',
      username: null,
      email: 'ann@example.com',
    })
    expect(setUser).toHaveBeenCalledWith(updated)
  })

  describe('username', () => {
    it('sets a username and saves', async () => {
      const setUser = vi.fn()
      mockAuth(baseUser, setUser)
      const updated: User = { ...baseUser, username: 'annm' }
      mockedUpdateUser.mockResolvedValue(updated)
      const user = userEvent.setup()
      render(<ProfileSettings />)

      await user.type(screen.getByLabelText('Username'), 'annm')
      await user.click(screen.getByRole('button', { name: 'Save Changes' }))

      expect(await screen.findByText('Profile updated.')).toBeInTheDocument()
      expect(mockedUpdateUser).toHaveBeenCalledWith(expect.objectContaining({ username: 'annm' }))
    })

    it('leaving username blank submits null, not an empty string', async () => {
      mockAuth(baseUser)
      mockedUpdateUser.mockResolvedValue(baseUser)
      const user = userEvent.setup()
      render(<ProfileSettings />)

      await user.click(screen.getByRole('button', { name: 'Save Changes' }))

      await screen.findByText('Profile updated.')
      expect(mockedUpdateUser).toHaveBeenCalledWith(expect.objectContaining({ username: null }))
    })

    it('validates format in real time, as the user types', async () => {
      mockAuth(baseUser)
      const user = userEvent.setup()
      render(<ProfileSettings />)

      await user.type(screen.getByLabelText('Username'), 'ab')

      expect(await screen.findByText(/between 3 and 30 characters/)).toBeInTheDocument()
      expect(mockedUpdateUser).not.toHaveBeenCalled()
    })

    it('attaches a duplicate-username error to the username field specifically', async () => {
      mockAuth(baseUser)
      mockedUpdateUser.mockRejectedValue({
        status: 409,
        message: 'This username is already taken',
      })
      const user = userEvent.setup()
      render(<ProfileSettings />)

      await user.type(screen.getByLabelText('Username'), 'taken_name')
      await user.click(screen.getByRole('button', { name: 'Save Changes' }))

      expect(await screen.findByText('This username is already taken')).toBeInTheDocument()
      expect(screen.getByLabelText('Username')).toHaveAttribute('aria-invalid', 'true')
      expect(screen.getByLabelText('Email Address')).not.toHaveAttribute('aria-invalid', 'true')
    })
  })

  it('attaches a duplicate-email error to the email field rather than a generic banner', async () => {
    mockAuth(baseUser)
    mockedUpdateUser.mockRejectedValue({
      status: 409,
      message: 'A user with this email is already registered',
    })
    const user = userEvent.setup()
    render(<ProfileSettings />)

    await user.clear(screen.getByLabelText('Email Address'))
    await user.type(screen.getByLabelText('Email Address'), 'taken@example.com')
    await user.click(screen.getByRole('button', { name: 'Save Changes' }))

    expect(
      await screen.findByText('A user with this email is already registered'),
    ).toBeInTheDocument()
  })

  it('shows a generic form error for a non-conflict failure', async () => {
    mockAuth(baseUser)
    mockedUpdateUser.mockRejectedValue({ status: null, message: 'Unable to reach the server.' })
    const user = userEvent.setup()
    render(<ProfileSettings />)

    await user.click(screen.getByRole('button', { name: 'Save Changes' }))

    expect(await screen.findByText('Unable to reach the server.')).toBeInTheDocument()
  })
})
