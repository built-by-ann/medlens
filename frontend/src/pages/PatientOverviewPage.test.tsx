import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PatientOverviewPage } from '@/pages/PatientOverviewPage'
import { archivePatient, getPatient } from '@/api/patients'
import type { Patient } from '@/types/api'

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    getPatient: vi.fn(),
    archivePatient: vi.fn(),
  }
})

const mockedGetPatient = vi.mocked(getPatient)
const mockedArchivePatient = vi.mocked(archivePatient)
const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()

  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

const patient: Patient = {
  id: 1,
  user_id: 1,
  first_name: 'Jane',
  last_name: 'Doe',
  date_of_birth: '1980-05-14',
  external_mrn: 'MRN-001',
  status: 'active',
  notes: 'Prefers morning appointments',
  created_at: '2026-01-01T12:00:00Z',
  updated_at: null,
}

function renderOverviewPage() {
  return render(
    <MemoryRouter initialEntries={['/patients/1']}>
      <Routes>
        <Route path="/patients/:patientId" element={<PatientOverviewPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('PatientOverviewPage', () => {
  beforeEach(() => {
    mockedGetPatient.mockReset()
    mockedArchivePatient.mockReset()
    mockNavigate.mockReset()
  })

  it('shows a loading state while the patient is being fetched', () => {
    mockedGetPatient.mockReturnValue(new Promise(() => {}))
    renderOverviewPage()

    expect(screen.getByRole('status')).toHaveTextContent('Loading patient')
  })

  it('displays the patient identity, demographic, and notes information', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    renderOverviewPage()

    expect(await screen.findByRole('heading', { name: 'Jane Doe' })).toBeInTheDocument()
    expect(screen.getByText('MRN-001')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Prefers morning appointments')).toBeInTheDocument()
  })

  it('shows a not-found error when the patient does not exist or is not owned by the user', async () => {
    mockedGetPatient.mockRejectedValue({ status: 404, message: 'Patient not found' })
    renderOverviewPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Patient not found')
  })

  it('links the Edit action to the patient edit route', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    renderOverviewPage()

    expect(await screen.findByRole('link', { name: 'Edit' })).toHaveAttribute(
      'href',
      '/patients/1/edit',
    )
  })

  it('opens an archive confirmation dialog naming the patient', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    const user = userEvent.setup()
    renderOverviewPage()

    await user.click(await screen.findByRole('button', { name: 'Archive' }))

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Archive Jane Doe?')).toBeInTheDocument()
    expect(mockedArchivePatient).not.toHaveBeenCalled()
  })

  it('cancels an archive without calling the API or navigating', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    const user = userEvent.setup()
    renderOverviewPage()

    await user.click(await screen.findByRole('button', { name: 'Archive' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(mockedArchivePatient).not.toHaveBeenCalled()
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('archives the patient and navigates back to the patients list on success', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedArchivePatient.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderOverviewPage()

    await user.click(await screen.findByRole('button', { name: 'Archive' }))
    await user.click(screen.getByRole('button', { name: 'Archive patient' }))

    await waitFor(() => expect(mockedArchivePatient).toHaveBeenCalledWith(1))
    expect(mockNavigate).toHaveBeenCalledWith('/patients')
  })

  it('shows an error in the dialog and does not navigate when archiving fails', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedArchivePatient.mockRejectedValue({ status: 500, message: 'Could not archive.' })
    const user = userEvent.setup()
    renderOverviewPage()

    await user.click(await screen.findByRole('button', { name: 'Archive' }))
    await user.click(screen.getByRole('button', { name: 'Archive patient' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not archive.')
    expect(mockNavigate).not.toHaveBeenCalled()
  })
})
