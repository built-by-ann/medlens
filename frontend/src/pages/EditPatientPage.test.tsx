import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { EditPatientPage } from '@/pages/EditPatientPage'
import { getPatient, updatePatient } from '@/api/patients'
import type { Patient } from '@/types/api'

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    getPatient: vi.fn(),
    updatePatient: vi.fn(),
  }
})

const mockedGetPatient = vi.mocked(getPatient)
const mockedUpdatePatient = vi.mocked(updatePatient)
const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()

  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

const existingPatient: Patient = {
  id: 1,
  user_id: 1,
  first_name: 'Jane',
  last_name: 'Doe',
  date_of_birth: '1980-05-14',
  external_mrn: 'MRN-001',
  status: 'active',
  notes: 'Prefers morning appointments',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
}

function renderEditPatientPage() {
  return render(
    <MemoryRouter initialEntries={['/patients/1/edit']}>
      <Routes>
        <Route path="/patients/:patientId/edit" element={<EditPatientPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('EditPatientPage', () => {
  beforeEach(() => {
    mockedGetPatient.mockReset()
    mockedUpdatePatient.mockReset()
    mockNavigate.mockReset()
  })

  it('shows a loading state while the patient is being fetched', () => {
    mockedGetPatient.mockReturnValue(new Promise(() => {}))
    renderEditPatientPage()

    expect(screen.getByRole('status')).toHaveTextContent('Loading patient')
  })

  it('prepopulates the form with the current patient values', async () => {
    mockedGetPatient.mockResolvedValue(existingPatient)
    renderEditPatientPage()

    expect(await screen.findByLabelText('First name')).toHaveValue('Jane')
    expect(screen.getByLabelText('Last name')).toHaveValue('Doe')
    expect(screen.getByLabelText('Date of birth')).toHaveValue('1980-05-14')
    expect(screen.getByLabelText('External MRN (optional)')).toHaveValue('MRN-001')
    expect(screen.getByLabelText('Notes (optional)')).toHaveValue('Prefers morning appointments')
  })

  it('shows an error state with retry when the patient fails to load', async () => {
    mockedGetPatient.mockRejectedValueOnce({ status: 404, message: 'Patient not found' })
    mockedGetPatient.mockResolvedValueOnce(existingPatient)
    const user = userEvent.setup()
    renderEditPatientPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Patient not found')

    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByLabelText('First name')).toHaveValue('Jane')
  })

  it('updates the patient and navigates to the overview page on success', async () => {
    mockedGetPatient.mockResolvedValue(existingPatient)
    mockedUpdatePatient.mockResolvedValue({ ...existingPatient, last_name: 'Smith' })
    const user = userEvent.setup()
    renderEditPatientPage()

    const lastNameInput = await screen.findByLabelText('Last name')
    await user.clear(lastNameInput)
    await user.type(lastNameInput, 'Smith')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() =>
      expect(mockedUpdatePatient).toHaveBeenCalledWith(1, {
        firstName: 'Jane',
        lastName: 'Smith',
        dateOfBirth: '1980-05-14',
        externalMrn: 'MRN-001',
        notes: 'Prefers morning appointments',
      }),
    )
    expect(mockNavigate).toHaveBeenCalledWith('/patients/1')
  })

  it('shows a server error and does not navigate when the update fails', async () => {
    mockedGetPatient.mockResolvedValue(existingPatient)
    mockedUpdatePatient.mockRejectedValue({ status: 500, message: 'Something went wrong.' })
    const user = userEvent.setup()
    renderEditPatientPage()

    await screen.findByLabelText('First name')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong.')
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('rejects an empty first name', async () => {
    mockedGetPatient.mockResolvedValue(existingPatient)
    const user = userEvent.setup()
    renderEditPatientPage()

    const firstNameInput = await screen.findByLabelText('First name')
    await user.clear(firstNameInput)
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByText('First name is required.')).toBeInTheDocument()
    expect(mockedUpdatePatient).not.toHaveBeenCalled()
  })

  it('has a cancel link back to the patient overview', async () => {
    mockedGetPatient.mockResolvedValue(existingPatient)
    renderEditPatientPage()

    await screen.findByLabelText('First name')
    expect(screen.getByRole('link', { name: 'Cancel' })).toHaveAttribute('href', '/patients/1')
  })

  it('shows a breadcrumb ending in "Edit patient" and a Back action to the patient overview', async () => {
    mockedGetPatient.mockResolvedValue(existingPatient)
    const user = userEvent.setup()
    renderEditPatientPage()

    const breadcrumb = await screen.findByRole('navigation', { name: 'Breadcrumb' })
    expect(within(breadcrumb).getByRole('link', { name: 'Jane Doe' })).toHaveAttribute(
      'href',
      '/patients/1',
    )
    expect(within(breadcrumb).getByText('Edit patient')).toHaveAttribute('aria-current', 'page')

    await user.click(screen.getByRole('button', { name: 'Back to Jane Doe' }))
    expect(mockNavigate).toHaveBeenCalledWith('/patients/1')
  })
})
