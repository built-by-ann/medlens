import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PatientsPage } from '@/pages/PatientsPage'
import { archivePatient, listPatients } from '@/api/patients'
import type { Patient } from '@/types/api'

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    listPatients: vi.fn(),
    archivePatient: vi.fn(),
  }
})

const mockedListPatients = vi.mocked(listPatients)
const mockedArchivePatient = vi.mocked(archivePatient)

const patientA: Patient = {
  id: 1,
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

const patientB: Patient = {
  id: 2,
  user_id: 1,
  first_name: 'John',
  last_name: 'Smith',
  date_of_birth: '1990-02-02',
  external_mrn: null,
  status: 'active',
  notes: null,
  created_at: '2026-01-02T00:00:00Z',
  updated_at: null,
}

function renderPatientsPage() {
  return render(
    <MemoryRouter initialEntries={['/patients']}>
      <PatientsPage />
    </MemoryRouter>,
  )
}

describe('PatientsPage', () => {
  beforeEach(() => {
    mockedListPatients.mockReset()
    mockedArchivePatient.mockReset()
  })

  it('shows a loading state while patients are being fetched', () => {
    mockedListPatients.mockReturnValue(new Promise(() => {}))
    renderPatientsPage()

    expect(screen.getByRole('status')).toHaveTextContent('Loading your patients')
  })

  it('shows the empty state with a create action when there are no patients', async () => {
    mockedListPatients.mockResolvedValue([])
    renderPatientsPage()

    expect(await screen.findByText('No patients yet')).toBeInTheDocument()
    const createLink = screen.getByRole('link', { name: 'Add a patient' })
    expect(createLink).toHaveAttribute('href', '/patients/new')
  })

  it('renders each patient with identifying information', async () => {
    mockedListPatients.mockResolvedValue([patientA, patientB])
    renderPatientsPage()

    expect(await screen.findByRole('link', { name: 'Jane Doe' })).toBeInTheDocument()
    expect(screen.getAllByText(/DOB: /)).toHaveLength(2)
    expect(screen.getByText('MRN: MRN-001')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'John Smith' })).toBeInTheDocument()
  })

  it('shows an error state with a retry action when the request fails, and recovers on retry', async () => {
    mockedListPatients.mockRejectedValueOnce({
      status: 500,
      message: 'Unable to reach the server.',
    })
    mockedListPatients.mockResolvedValueOnce([patientA])

    const user = userEvent.setup()
    renderPatientsPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to reach the server.')

    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('link', { name: 'Jane Doe' })).toBeInTheDocument()
    expect(mockedListPatients).toHaveBeenCalledTimes(2)
  })

  it('searches by first or last name', async () => {
    mockedListPatients.mockResolvedValue([patientA, patientB])
    const user = userEvent.setup()
    renderPatientsPage()

    await screen.findByRole('link', { name: 'Jane Doe' })
    await user.type(screen.getByLabelText('Search patients'), 'smith')

    expect(screen.queryByRole('link', { name: 'Jane Doe' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'John Smith' })).toBeInTheDocument()
  })

  it('searches by external MRN', async () => {
    mockedListPatients.mockResolvedValue([patientA, patientB])
    const user = userEvent.setup()
    renderPatientsPage()

    await screen.findByRole('link', { name: 'Jane Doe' })
    await user.type(screen.getByLabelText('Search patients'), 'mrn-001')

    expect(screen.getByRole('link', { name: 'Jane Doe' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'John Smith' })).not.toBeInTheDocument()
  })

  it('shows a no-results message, distinct from the empty state, when a search matches nothing', async () => {
    mockedListPatients.mockResolvedValue([patientA])
    const user = userEvent.setup()
    renderPatientsPage()

    await screen.findByRole('link', { name: 'Jane Doe' })
    await user.type(screen.getByLabelText('Search patients'), 'nonexistent')

    expect(screen.getByText('No patients match your search.')).toBeInTheDocument()
    expect(screen.queryByText('No patients yet')).not.toBeInTheDocument()
  })

  it('search is case-insensitive', async () => {
    mockedListPatients.mockResolvedValue([patientA])
    const user = userEvent.setup()
    renderPatientsPage()

    await screen.findByRole('link', { name: 'Jane Doe' })
    await user.type(screen.getByLabelText('Search patients'), 'JANE')

    expect(screen.getByRole('link', { name: 'Jane Doe' })).toBeInTheDocument()
  })

  it('opens an archive confirmation dialog naming the patient', async () => {
    mockedListPatients.mockResolvedValue([patientA])
    const user = userEvent.setup()
    renderPatientsPage()

    await screen.findByRole('link', { name: 'Jane Doe' })
    await user.click(screen.getByRole('button', { name: 'Archive Jane Doe' }))

    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText('Archive Jane Doe?')).toBeInTheDocument()
    expect(mockedArchivePatient).not.toHaveBeenCalled()
  })

  it('cancels an archive without calling the API', async () => {
    mockedListPatients.mockResolvedValue([patientA])
    const user = userEvent.setup()
    renderPatientsPage()

    await screen.findByRole('link', { name: 'Jane Doe' })
    await user.click(screen.getByRole('button', { name: 'Archive Jane Doe' }))

    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))

    expect(mockedArchivePatient).not.toHaveBeenCalled()
    expect(screen.getByRole('link', { name: 'Jane Doe' })).toBeInTheDocument()
  })

  it('dismisses the archive dialog with the Escape key, without calling the API', async () => {
    mockedListPatients.mockResolvedValue([patientA])
    const user = userEvent.setup()
    renderPatientsPage()

    await screen.findByRole('link', { name: 'Jane Doe' })
    await user.click(screen.getByRole('button', { name: 'Archive Jane Doe' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    await user.keyboard('{Escape}')

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(mockedArchivePatient).not.toHaveBeenCalled()
  })

  it('archives a patient and removes it from the list on success', async () => {
    mockedListPatients.mockResolvedValue([patientA, patientB])
    mockedArchivePatient.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderPatientsPage()

    await screen.findByRole('link', { name: 'Jane Doe' })
    await user.click(screen.getByRole('button', { name: 'Archive Jane Doe' }))

    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Archive patient' }))

    await waitFor(() => expect(mockedArchivePatient).toHaveBeenCalledWith(1))
    expect(screen.queryByRole('link', { name: 'Jane Doe' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'John Smith' })).toBeInTheDocument()
  })

  it('shows an error inside the dialog and keeps the patient when archiving fails', async () => {
    mockedListPatients.mockResolvedValue([patientA])
    mockedArchivePatient.mockRejectedValue({ status: 500, message: 'Could not archive.' })
    const user = userEvent.setup()
    renderPatientsPage()

    await screen.findByRole('link', { name: 'Jane Doe' })
    await user.click(screen.getByRole('button', { name: 'Archive Jane Doe' }))

    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Archive patient' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Could not archive.')
    expect(screen.getByRole('link', { name: 'Jane Doe' })).toBeInTheDocument()
  })
})
