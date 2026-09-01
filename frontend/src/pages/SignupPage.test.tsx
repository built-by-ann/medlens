import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SignupPage } from '@/pages/SignupPage'
import { registerUser } from '@/api/auth'

vi.mock('@/api/auth')

const mockedRegisterUser = vi.mocked(registerUser)
const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()

  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

function renderSignupPage() {
  return render(
    <MemoryRouter initialEntries={['/signup']}>
      <SignupPage />
    </MemoryRouter>,
  )
}

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Full Name'), 'Jane Doe')
  await user.type(screen.getByLabelText('Username'), 'jane_doe')
  await user.type(screen.getByLabelText('Email'), 'jane@example.com')
  await user.type(screen.getByLabelText('Password'), 'correcthorse123')
  await user.type(screen.getByLabelText('Confirm Password'), 'correcthorse123')
}

describe('SignupPage', () => {
  beforeEach(() => {
    mockedRegisterUser.mockReset()
    mockNavigate.mockReset()
  })

  it('shows inline validation errors and does not call registerUser when fields are empty', async () => {
    const user = userEvent.setup()
    renderSignupPage()

    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByText('Full name is required.')).toBeInTheDocument()
    expect(screen.getByText('Username is required.')).toBeInTheDocument()
    expect(screen.getByText('Email is required.')).toBeInTheDocument()
    expect(screen.getByText('Password is required.')).toBeInTheDocument()
    expect(screen.getByText('Please confirm your password.')).toBeInTheDocument()
    expect(mockedRegisterUser).not.toHaveBeenCalled()
  })

  it('rejects a password shorter than 8 characters', async () => {
    const user = userEvent.setup()
    renderSignupPage()

    await user.type(screen.getByLabelText('Full Name'), 'Jane Doe')
    await user.type(screen.getByLabelText('Username'), 'jane_doe')
    await user.type(screen.getByLabelText('Email'), 'jane@example.com')
    await user.type(screen.getByLabelText('Password'), 'short')
    await user.type(screen.getByLabelText('Confirm Password'), 'short')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByText('Password must be at least 8 characters.')).toBeInTheDocument()
    expect(mockedRegisterUser).not.toHaveBeenCalled()
  })

  it('rejects mismatched password confirmation', async () => {
    const user = userEvent.setup()
    renderSignupPage()

    await user.type(screen.getByLabelText('Full Name'), 'Jane Doe')
    await user.type(screen.getByLabelText('Username'), 'jane_doe')
    await user.type(screen.getByLabelText('Email'), 'jane@example.com')
    await user.type(screen.getByLabelText('Password'), 'correcthorse123')
    await user.type(screen.getByLabelText('Confirm Password'), 'somethingelse')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByText('Passwords do not match.')).toBeInTheDocument()
    expect(mockedRegisterUser).not.toHaveBeenCalled()
  })

  describe('username field', () => {
    it('validates format in real time, as the user types, not only on submit', async () => {
      const user = userEvent.setup()
      renderSignupPage()

      await user.type(screen.getByLabelText('Username'), 'ab')

      expect(await screen.findByText(/between 3 and 30 characters/)).toBeInTheDocument()
      // Never submitted; this is purely a live-typing check.
      expect(mockedRegisterUser).not.toHaveBeenCalled()
    })

    it('clears the live validation error once the value becomes valid', async () => {
      const user = userEvent.setup()
      renderSignupPage()

      const usernameInput = screen.getByLabelText('Username')
      await user.type(usernameInput, 'ab')
      expect(await screen.findByText(/between 3 and 30 characters/)).toBeInTheDocument()

      await user.type(usernameInput, 'c')

      expect(screen.queryByText(/between 3 and 30 characters/)).not.toBeInTheDocument()
    })

    it('flags disallowed characters as the user types', async () => {
      const user = userEvent.setup()
      renderSignupPage()

      await user.type(screen.getByLabelText('Username'), 'not valid!')

      expect(
        await screen.findByText(/letters, numbers, underscores, and periods/),
      ).toBeInTheDocument()
    })

    it('rejects an empty username on submit', async () => {
      const user = userEvent.setup()
      renderSignupPage()

      await user.type(screen.getByLabelText('Full Name'), 'Jane Doe')
      await user.type(screen.getByLabelText('Email'), 'jane@example.com')
      await user.type(screen.getByLabelText('Password'), 'correcthorse123')
      await user.type(screen.getByLabelText('Confirm Password'), 'correcthorse123')
      await user.click(screen.getByRole('button', { name: 'Create account' }))

      expect(await screen.findByText('Username is required.')).toBeInTheDocument()
      expect(mockedRegisterUser).not.toHaveBeenCalled()
    })
  })

  it('submits trimmed values and redirects to Login on success, without logging in', async () => {
    mockedRegisterUser.mockResolvedValue({
      id: 1,
      email: 'jane@example.com',
      username: 'jane_doe',
      name: 'Jane Doe',
      created_at: '2026-01-01T00:00:00Z',
    })
    const user = userEvent.setup()
    renderSignupPage()

    await user.type(screen.getByLabelText('Full Name'), '  Jane Doe  ')
    await user.type(screen.getByLabelText('Username'), '  jane_doe  ')
    await user.type(screen.getByLabelText('Email'), '  jane@example.com  ')
    await user.type(screen.getByLabelText('Password'), 'correcthorse123')
    await user.type(screen.getByLabelText('Confirm Password'), 'correcthorse123')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    await waitFor(() =>
      expect(mockedRegisterUser).toHaveBeenCalledWith({
        email: 'jane@example.com',
        password: 'correcthorse123',
        username: 'jane_doe',
        name: 'Jane Doe',
      }),
    )
    expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true })
  })

  it('attaches a duplicate-email (409) error to the email field specifically', async () => {
    mockedRegisterUser.mockRejectedValue({
      status: 409,
      message: 'A user with this email is already registered',
    })
    const user = userEvent.setup()
    renderSignupPage()

    await fillValidForm(user)
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(
      await screen.findByText('A user with this email is already registered'),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true')
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('attaches a duplicate-username (409) error to the username field specifically', async () => {
    mockedRegisterUser.mockRejectedValue({
      status: 409,
      message: 'This username is already taken',
    })
    const user = userEvent.setup()
    renderSignupPage()

    await fillValidForm(user)
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByText('This username is already taken')).toBeInTheDocument()
    expect(screen.getByLabelText('Username')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('Email')).not.toHaveAttribute('aria-invalid', 'true')
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('shows a form-level error for a non-409 backend failure', async () => {
    mockedRegisterUser.mockRejectedValue({
      status: 500,
      message: 'Something went wrong.',
    })
    const user = userEvent.setup()
    renderSignupPage()

    await fillValidForm(user)
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong.')
    expect(screen.getByLabelText('Email')).not.toHaveAttribute('aria-invalid', 'true')
  })

  it('disables the submit button and inputs while submitting', async () => {
    let resolveRegister: () => void = () => {}
    mockedRegisterUser.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRegister = () =>
            resolve({
              id: 1,
              email: 'jane@example.com',
              username: 'jane_doe',
              name: 'Jane Doe',
              created_at: '2026-01-01T00:00:00Z',
            })
        }),
    )
    const user = userEvent.setup()
    renderSignupPage()

    await fillValidForm(user)
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Creating account...' })).toBeDisabled()
    })
    expect(screen.getByLabelText('Full Name')).toBeDisabled()
    expect(screen.getByLabelText('Username')).toBeDisabled()
    expect(screen.getByLabelText('Email')).toBeDisabled()
    expect(screen.getByLabelText('Password')).toBeDisabled()
    expect(screen.getByLabelText('Confirm Password')).toBeDisabled()

    resolveRegister()

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true })
    })
  })
})
