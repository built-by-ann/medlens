import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DashboardPage } from '@/pages/DashboardPage'
import { useAuth } from '@/hooks/useAuth'
import { archivePatient, listPatients } from '@/api/patients'
import type { Patient } from '@/types/api'

vi.mock('@/hooks/useAuth')

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    listPatients: vi.fn(),
    archivePatient: vi.fn(),
  }
})

const mockedUseAuth = vi.mocked(useAuth)
const mockedListPatients = vi.mocked(listPatients)
const mockedArchivePatient = vi.mocked(archivePatient)

function makePatient(overrides: Partial<Patient>): Patient {
  return {
    id: 1,
    user_id: 1,
    first_name: 'Jane',
    last_name: 'Doe',
    date_of_birth: '1980-05-14',
    external_mrn: null,
    status: 'active',
    notes: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    ...overrides,
  }
}

const olderPatient = makePatient({
  id: 1,
  first_name: 'Jane',
  last_name: 'Doe',
  external_mrn: 'MRN-001',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
})

const recentlyUpdatedPatient = makePatient({
  id: 2,
  first_name: 'John',
  last_name: 'Smith',
  external_mrn: 'MRN-002',
  created_at: '2026-01-02T00:00:00Z',
  updated_at: '2026-01-10T00:00:00Z',
})

function renderDashboard() {
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <DashboardPage />
    </MemoryRouter>,
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    mockedListPatients.mockReset()
    mockedArchivePatient.mockReset()
    mockedUseAuth.mockReturnValue({
      user: { id: 1, email: 'a@example.com', name: 'Jane', created_at: '2026-01-01T00:00:00Z' },
      token: 'token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
    })
  })

  it('shows a welcome header naming the user', async () => {
    mockedListPatients.mockResolvedValue([])
    renderDashboard()

    expect(screen.getByRole('heading', { name: /Welcome back, Jane/ })).toBeInTheDocument()
  })

  it('falls back to a generic welcome message when the user has no name', async () => {
    mockedListPatients.mockResolvedValue([])
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

  it('shows a loading state while patients are being fetched', () => {
    mockedListPatients.mockReturnValue(new Promise(() => {}))
    renderDashboard()

    expect(screen.getByRole('status')).toHaveTextContent('Loading your patients')
  })

  it('shows an error state with a retry action', async () => {
    mockedListPatients.mockRejectedValueOnce({ status: 500, message: 'Server error.' })
    mockedListPatients.mockResolvedValueOnce([olderPatient])
    const user = userEvent.setup()
    renderDashboard()

    expect(await screen.findByRole('alert')).toHaveTextContent('Server error.')

    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('Jane Doe')).toBeInTheDocument()
  })

  it('shows a welcoming empty state with a create action when there are no patients at all', async () => {
    mockedListPatients.mockResolvedValue([])
    renderDashboard()

    expect(await screen.findByText('No patients yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Add a patient' })).toHaveAttribute(
      'href',
      '/patients/new',
    )
    // No search box or quick actions when there is nothing to search or act on.
    expect(screen.queryByLabelText('Search patients')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '+ New patient' })).not.toBeInTheDocument()
  })

  it('shows recent patients, most recently updated first, with status and updated date', async () => {
    mockedListPatients.mockResolvedValue([olderPatient, recentlyUpdatedPatient])
    renderDashboard()

    expect(await screen.findByRole('heading', { name: 'Recent patients' })).toBeInTheDocument()

    const links = screen.getAllByRole('link', { name: /Jane Doe|John Smith/ })
    expect(links[0]).toHaveTextContent('John Smith')
    expect(links[1]).toHaveTextContent('Jane Doe')

    expect(screen.getByText('MRN: MRN-002')).toBeInTheDocument()
    expect(screen.getAllByText('Status: Active')).toHaveLength(2)
    expect(screen.getByText(/Updated: /)).toBeInTheDocument()
  })

  it('limits recent patients to the top 3', async () => {
    const patients = Array.from({ length: 7 }, (_, index) =>
      makePatient({
        id: index + 1,
        first_name: `Patient${index + 1}`,
        created_at: `2026-01-0${(index % 9) + 1}T00:00:00Z`,
      }),
    )
    mockedListPatients.mockResolvedValue(patients)
    renderDashboard()

    await screen.findByRole('heading', { name: 'Recent patients' })
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
  })

  it('search updates live and searches the full patient list, not just the recent preview', async () => {
    mockedListPatients.mockResolvedValue([olderPatient, recentlyUpdatedPatient])
    const user = userEvent.setup()
    renderDashboard()

    await screen.findByRole('heading', { name: 'Recent patients' })

    await user.type(screen.getByLabelText('Search patients'), 'Jane')

    expect(await screen.findByRole('heading', { name: 'Search results' })).toBeInTheDocument()
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    expect(screen.queryByText('John Smith')).not.toBeInTheDocument()
  })

  it('searches by MRN', async () => {
    mockedListPatients.mockResolvedValue([olderPatient, recentlyUpdatedPatient])
    const user = userEvent.setup()
    renderDashboard()

    await screen.findByRole('heading', { name: 'Recent patients' })
    await user.type(screen.getByLabelText('Search patients'), 'MRN-002')

    expect(await screen.findByText('John Smith')).toBeInTheDocument()
    expect(screen.queryByText('Jane Doe')).not.toBeInTheDocument()
  })

  it('shows a no-match state when the search term matches nothing', async () => {
    mockedListPatients.mockResolvedValue([olderPatient])
    const user = userEvent.setup()
    renderDashboard()

    await screen.findByRole('heading', { name: 'Recent patients' })
    await user.type(screen.getByLabelText('Search patients'), 'nonexistent')

    expect(await screen.findByText('No patients match your search.')).toBeInTheDocument()
  })

  it('shows quick actions linking to New Patient and Patients', async () => {
    mockedListPatients.mockResolvedValue([olderPatient])
    renderDashboard()

    expect(await screen.findByRole('link', { name: '+ New patient' })).toHaveAttribute(
      'href',
      '/patients/new',
    )
    expect(screen.getByRole('link', { name: 'View all patients' })).toHaveAttribute(
      'href',
      '/patients',
    )
  })

  it('does not offer an Upload Document quick action, since it has no patient-less destination', async () => {
    mockedListPatients.mockResolvedValue([olderPatient])
    renderDashboard()

    await screen.findByRole('heading', { name: 'Recent patients' })
    expect(screen.queryByRole('link', { name: /Upload/ })).not.toBeInTheDocument()
  })

  it('opens an archive confirmation dialog from a recent patient card', async () => {
    mockedListPatients.mockResolvedValue([olderPatient])
    const user = userEvent.setup()
    renderDashboard()

    await user.click(await screen.findByRole('button', { name: 'Archive Jane Doe' }))

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Archive Jane Doe?')).toBeInTheDocument()
  })

  it('archives a patient directly from the dashboard', async () => {
    mockedListPatients.mockResolvedValue([olderPatient])
    mockedArchivePatient.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderDashboard()

    await user.click(await screen.findByRole('button', { name: 'Archive Jane Doe' }))
    await user.click(screen.getByRole('button', { name: 'Archive patient' }))

    await waitFor(() => expect(mockedArchivePatient).toHaveBeenCalledWith(1))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })
})
