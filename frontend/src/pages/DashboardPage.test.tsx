import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DashboardPage } from '@/pages/DashboardPage'
import { useAuth } from '@/hooks/useAuth'
import { archivePatient, listPatients } from '@/api/patients'
import { getRecentAnalyses } from '@/api/analyses'
import type { Patient, RecentAnalysis } from '@/types/api'

vi.mock('@/hooks/useAuth')

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    listPatients: vi.fn(),
    archivePatient: vi.fn(),
  }
})

vi.mock('@/api/analyses', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/analyses')>()

  return {
    ...actual,
    getRecentAnalyses: vi.fn(),
  }
})

const mockedUseAuth = vi.mocked(useAuth)
const mockedListPatients = vi.mocked(listPatients)
const mockedArchivePatient = vi.mocked(archivePatient)
const mockedGetRecentAnalyses = vi.mocked(getRecentAnalyses)

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

function makeRecentAnalysis(overrides: Partial<RecentAnalysis> = {}): RecentAnalysis {
  return {
    id: 1,
    patient_id: 1,
    status: 'completed',
    created_at: '2026-01-01T12:00:00Z',
    completed_at: '2026-01-01T12:05:00Z',
    error_message: null,
    summary: 'Reconciliation completed with 1 finding.',
    document_count: 1,
    total_findings: 1,
    high_severity_findings: 1,
    medium_severity_findings: 0,
    low_severity_findings: 0,
    open_findings: 0,
    provider: 'gemini',
    model_name: 'gemini-2.0-flash',
    patient: { id: 1, first_name: 'Jane', last_name: 'Doe' },
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
      <Routes>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/patients/:patientId/analyses/new" element={<div>Create Analysis stub</div>} />
        <Route
          path="/patients/:patientId/analyses/:analysisId"
          element={<div>Analysis Detail stub</div>}
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    mockedListPatients.mockReset()
    mockedArchivePatient.mockReset()
    mockedGetRecentAnalyses.mockReset()
    mockedGetRecentAnalyses.mockResolvedValue([])
    mockedUseAuth.mockReturnValue({
      user: {
        id: 1,
        email: 'a@example.com',
        name: 'Jane',
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

  it('shows a welcome header naming the user', async () => {
    mockedListPatients.mockResolvedValue([])
    renderDashboard()

    expect(screen.getByRole('heading', { name: /Welcome back, Jane/ })).toBeInTheDocument()
  })

  it('falls back to a generic welcome message when the user has no name', async () => {
    mockedListPatients.mockResolvedValue([])
    mockedUseAuth.mockReturnValue({
      user: {
        id: 1,
        email: 'a@example.com',
        name: null,
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

    renderDashboard()

    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })

  it('shows a loading state while patients are being fetched', () => {
    mockedListPatients.mockReturnValue(new Promise(() => {}))
    renderDashboard()

    // Recent Analyses loads independently and in parallel, so this checks
    // the specific "Loading your patients" text rather than a bare
    // role="status" query, which could match either section's spinner.
    expect(screen.getByText('Loading your patients')).toBeInTheDocument()
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

  it('shows a "Recent patients" heading even with no patients, aligning with Recent Analyses', async () => {
    mockedListPatients.mockResolvedValue([])
    renderDashboard()

    // Both columns' cards start below a heading in every state; keeps the
    // two side-by-side cards the same height instead of one sitting flush
    // with the top of the grid row.
    expect(await screen.findByRole('heading', { name: 'Recent patients' })).toBeInTheDocument()
  })

  it('shows a welcoming empty state with a create action when there are no patients at all', async () => {
    mockedListPatients.mockResolvedValue([])
    renderDashboard()

    expect(await screen.findByText('No patients yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Add a patient' })).toHaveAttribute(
      'href',
      '/patients/new',
    )
    // No search box when there is nothing to search, but Quick Actions
    // (including "+ New patient") stays visible; it's meant to be reachable
    // near the top of the Dashboard regardless of whether any patients exist.
    expect(screen.queryByLabelText('Search patients')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '+ New patient' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '+ New Analysis' })).toBeDisabled()
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

    // The heading itself renders on the very first paint, regardless of
    // loading state (see DashboardPage.tsx); it's not a reliable "patients
    // have loaded" signal on its own, so the actual list items are what's
    // awaited here.
    expect(await screen.findAllByRole('listitem')).toHaveLength(3)
  })

  it('search updates live and searches the full patient list, not just the recent preview', async () => {
    mockedListPatients.mockResolvedValue([olderPatient, recentlyUpdatedPatient])
    const user = userEvent.setup()
    renderDashboard()

    // findByLabelText, not getByLabelText: the search box only renders once
    // patients have actually loaded (patients.length > 0); the "Recent
    // patients" heading above it renders immediately regardless of loading
    // state, so waiting on the heading alone doesn't guarantee the search
    // box exists yet.
    await user.type(await screen.findByLabelText('Search patients'), 'Jane')

    expect(await screen.findByRole('heading', { name: 'Search results' })).toBeInTheDocument()
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    expect(screen.queryByText('John Smith')).not.toBeInTheDocument()
  })

  it('searches by MRN', async () => {
    mockedListPatients.mockResolvedValue([olderPatient, recentlyUpdatedPatient])
    const user = userEvent.setup()
    renderDashboard()

    await user.type(await screen.findByLabelText('Search patients'), 'MRN-002')

    expect(await screen.findByText('John Smith')).toBeInTheDocument()
    expect(screen.queryByText('Jane Doe')).not.toBeInTheDocument()
  })

  it('shows a no-match state when the search term matches nothing', async () => {
    mockedListPatients.mockResolvedValue([olderPatient])
    const user = userEvent.setup()
    renderDashboard()

    await user.type(await screen.findByLabelText('Search patients'), 'nonexistent')

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

    expect(screen.getByRole('dialog', { name: 'Archive Jane Doe?' })).toBeInTheDocument()
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

  describe('starting an analysis from the Dashboard', () => {
    it('disables + New Analysis when there are no patients yet', async () => {
      mockedListPatients.mockResolvedValue([])
      renderDashboard()

      expect(await screen.findByRole('button', { name: '+ New Analysis' })).toBeDisabled()
    })

    it('opens a searchable patient picker', async () => {
      mockedListPatients.mockResolvedValue([olderPatient, recentlyUpdatedPatient])
      const user = userEvent.setup()
      renderDashboard()

      await user.click(await screen.findByRole('button', { name: '+ New Analysis' }))

      const dialog = screen.getByRole('dialog', { name: 'Start an analysis' })
      expect(within(dialog).getByRole('button', { name: /Jane Doe/ })).toBeInTheDocument()
      expect(within(dialog).getByRole('button', { name: /John Smith/ })).toBeInTheDocument()
    })

    it('filters the patient picker using the same search behavior as Recent Patients', async () => {
      mockedListPatients.mockResolvedValue([olderPatient, recentlyUpdatedPatient])
      const user = userEvent.setup()
      renderDashboard()

      await user.click(await screen.findByRole('button', { name: '+ New Analysis' }))
      const dialog = screen.getByRole('dialog', { name: 'Start an analysis' })

      await user.type(within(dialog).getByLabelText('Search patients'), 'Smith')

      expect(within(dialog).queryByRole('button', { name: /Jane Doe/ })).not.toBeInTheDocument()
      expect(within(dialog).getByRole('button', { name: /John Smith/ })).toBeInTheDocument()
    })

    it('selecting a patient navigates straight into that patient’s Create Analysis workflow', async () => {
      mockedListPatients.mockResolvedValue([olderPatient])
      const user = userEvent.setup()
      renderDashboard()

      await user.click(await screen.findByRole('button', { name: '+ New Analysis' }))
      const dialog = screen.getByRole('dialog', { name: 'Start an analysis' })
      await user.click(within(dialog).getByRole('button', { name: /Jane Doe/ }))

      expect(await screen.findByText('Create Analysis stub')).toBeInTheDocument()
    })

    it('canceling the picker closes it without navigating anywhere', async () => {
      mockedListPatients.mockResolvedValue([olderPatient])
      const user = userEvent.setup()
      renderDashboard()

      await user.click(await screen.findByRole('button', { name: '+ New Analysis' }))
      await user.click(screen.getByRole('button', { name: 'Cancel' }))

      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(screen.queryByText('Create Analysis stub')).not.toBeInTheDocument()
    })
  })

  describe('Recent Analyses', () => {
    it('shows a loading state while recent analyses are being fetched', async () => {
      mockedListPatients.mockResolvedValue([])
      mockedGetRecentAnalyses.mockReturnValue(new Promise(() => {}))
      renderDashboard()

      expect(await screen.findByText('Loading recent analyses')).toBeInTheDocument()
    })

    it('shows an empty state when there are no analyses yet', async () => {
      mockedListPatients.mockResolvedValue([])
      renderDashboard()

      expect(await screen.findByText(/No analyses yet/)).toBeInTheDocument()
    })

    it('disables its own "Start an analysis" button when there are no patients yet, matching Quick Actions', async () => {
      mockedListPatients.mockResolvedValue([])
      renderDashboard()

      expect(
        await screen.findByText(/Add your first patient, then start an analysis/),
      ).toBeInTheDocument()
      expect(await screen.findByRole('button', { name: 'Start an analysis' })).toBeDisabled()
    })

    it('enables its own "Start an analysis" button once a patient exists, opening the same picker as Quick Actions', async () => {
      mockedListPatients.mockResolvedValue([olderPatient])
      const user = userEvent.setup()
      renderDashboard()

      const button = await screen.findByRole('button', { name: 'Start an analysis' })
      expect(button).toBeEnabled()

      await user.click(button)

      expect(screen.getByRole('dialog', { name: 'Start an analysis' })).toBeInTheDocument()
    })

    it('shows an error state with its own retry action', async () => {
      mockedListPatients.mockResolvedValue([])
      mockedGetRecentAnalyses.mockRejectedValueOnce({ status: 500, message: 'Server error.' })
      mockedGetRecentAnalyses.mockResolvedValueOnce([makeRecentAnalysis()])
      const user = userEvent.setup()
      renderDashboard()

      expect(await screen.findByText('Server error.')).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'Try again' }))

      expect(await screen.findByText('Jane Doe', { selector: 'span' })).toBeInTheDocument()
    })

    it('identifies the patient and links to the Analysis Results page', async () => {
      mockedListPatients.mockResolvedValue([])
      mockedGetRecentAnalyses.mockResolvedValue([
        makeRecentAnalysis({
          id: 42,
          patient_id: 7,
          patient: { id: 7, first_name: 'Jane', last_name: 'Doe' },
        }),
      ])
      renderDashboard()

      const link = await screen.findByRole('link', { name: /View analysis for Jane Doe/ })
      expect(link).toHaveAttribute('href', '/patients/7/analyses/42')
      expect(screen.getByText('Jane Doe', { selector: 'span' })).toBeInTheDocument()
    })

    it('navigates to the Analysis Results page when clicked', async () => {
      mockedListPatients.mockResolvedValue([])
      mockedGetRecentAnalyses.mockResolvedValue([makeRecentAnalysis({ id: 42, patient_id: 7 })])
      const user = userEvent.setup()
      renderDashboard()

      await user.click(await screen.findByRole('link', { name: /View analysis for Jane Doe/ }))

      expect(await screen.findByText('Analysis Detail stub')).toBeInTheDocument()
    })
  })
})
