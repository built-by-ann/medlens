import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NewPatientPage } from '@/pages/NewPatientPage'
import { createPatient } from '@/api/patients'
import type { Patient } from '@/types/api'

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    createPatient: vi.fn(),
  }
})

const mockedCreatePatient = vi.mocked(createPatient)
const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()

  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

const createdPatient: Patient = {
  id: 5,
  user_id: 1,
  first_name: 'Jane',
  last_name: 'Doe',
  date_of_birth: '1980-05-14',
  external_mrn: 'MRN-001',
  status: 'active',
  notes: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
}

function renderNewPatientPage() {
  return render(
    <MemoryRouter initialEntries={['/patients/new']}>
      <NewPatientPage />
    </MemoryRouter>,
  )
}

describe('NewPatientPage', () => {
  beforeEach(() => {
    mockedCreatePatient.mockReset()
    mockNavigate.mockReset()
  })

  it('shows validation messages and does not submit when required fields are missing', async () => {
    const user = userEvent.setup()
    renderNewPatientPage()

    await user.click(screen.getByRole('button', { name: 'Create patient' }))

    expect(await screen.findByText('First name is required.')).toBeInTheDocument()
    expect(screen.getByText('Last name is required.')).toBeInTheDocument()
    expect(screen.getByText('Date of birth is required.')).toBeInTheDocument()
    expect(mockedCreatePatient).not.toHaveBeenCalled()
  })

  it('creates a patient and navigates to their overview page on success', async () => {
    mockedCreatePatient.mockResolvedValue(createdPatient)
    const user = userEvent.setup()
    renderNewPatientPage()

    await user.type(screen.getByLabelText('First name'), 'Jane')
    await user.type(screen.getByLabelText('Last name'), 'Doe')
    await user.type(screen.getByLabelText('Date of birth'), '1980-05-14')
    await user.type(screen.getByLabelText('External MRN (optional)'), 'MRN-001')
    await user.click(screen.getByRole('button', { name: 'Create patient' }))

    await waitFor(() =>
      expect(mockedCreatePatient).toHaveBeenCalledWith({
        firstName: 'Jane',
        lastName: 'Doe',
        dateOfBirth: '1980-05-14',
        externalMrn: 'MRN-001',
        notes: '',
      }),
    )
    expect(mockNavigate).toHaveBeenCalledWith('/patients/5')
  })

  it('shows a server error and does not navigate when creation fails', async () => {
    mockedCreatePatient.mockRejectedValue({ status: 500, message: 'Something went wrong.' })
    const user = userEvent.setup()
    renderNewPatientPage()

    await user.type(screen.getByLabelText('First name'), 'Jane')
    await user.type(screen.getByLabelText('Last name'), 'Doe')
    await user.type(screen.getByLabelText('Date of birth'), '1980-05-14')
    await user.click(screen.getByRole('button', { name: 'Create patient' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong.')
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('disables the submit button while saving and prevents duplicate submissions', async () => {
    let resolveCreate: (patient: Patient) => void = () => {}
    mockedCreatePatient.mockReturnValue(
      new Promise((resolve) => {
        resolveCreate = resolve
      }),
    )
    const user = userEvent.setup()
    renderNewPatientPage()

    await user.type(screen.getByLabelText('First name'), 'Jane')
    await user.type(screen.getByLabelText('Last name'), 'Doe')
    await user.type(screen.getByLabelText('Date of birth'), '1980-05-14')

    const submitButton = screen.getByRole('button', { name: 'Create patient' })
    await user.click(submitButton)

    expect(await screen.findByRole('button', { name: 'Saving...' })).toBeDisabled()

    resolveCreate(createdPatient)
    await waitFor(() => expect(mockedCreatePatient).toHaveBeenCalledTimes(1))
  })

  it('has a cancel link back to the patients list', () => {
    renderNewPatientPage()

    expect(screen.getByRole('link', { name: 'Cancel' })).toHaveAttribute('href', '/patients')
  })
})
