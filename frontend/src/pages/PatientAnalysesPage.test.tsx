import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PatientAnalysesPage } from '@/pages/PatientAnalysesPage'
import { getPatient } from '@/api/patients'
import { deleteAnalysis, listAnalyses } from '@/api/analyses'
import type { AnalysisSummary, Patient } from '@/types/api'

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    getPatient: vi.fn(),
  }
})

vi.mock('@/api/analyses', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/analyses')>()

  return {
    ...actual,
    listAnalyses: vi.fn(),
    deleteAnalysis: vi.fn(),
  }
})

const mockedGetPatient = vi.mocked(getPatient)
const mockedListAnalyses = vi.mocked(listAnalyses)
const mockedDeleteAnalysis = vi.mocked(deleteAnalysis)

const patient: Patient = {
  id: 7,
  user_id: 1,
  first_name: 'Jane',
  last_name: 'Doe',
  date_of_birth: '1980-05-14',
  external_mrn: null,
  status: 'active',
  notes: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
}

const sampleAnalysis: AnalysisSummary = {
  id: 42,
  patient_id: 7,
  status: 'completed',
  created_at: '2026-01-01T12:00:00Z',
  completed_at: '2026-01-01T12:05:00Z',
  error_message: null,
  summary: 'Reconciliation completed with 1 finding.',
  document_count: 2,
  total_findings: 1,
  high_severity_findings: 1,
  medium_severity_findings: 0,
  low_severity_findings: 0,
  provider: 'gemini',
  model_name: 'gemini-2.0-flash',
}

function renderPage(state: { flashMessage?: string } | null = null) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/patients/7/analyses', state }]}>
      <Routes>
        <Route path="/patients/:patientId/analyses" element={<PatientAnalysesPage />} />
        <Route path="/patients/:patientId" element={<div>Patient Overview stub</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('PatientAnalysesPage', () => {
  beforeEach(() => {
    mockedGetPatient.mockReset()
    mockedListAnalyses.mockReset()
    mockedDeleteAnalysis.mockReset()
    mockedGetPatient.mockResolvedValue(patient)
    mockedListAnalyses.mockResolvedValue([])
  })

  it('shows a loading state while the patient is being fetched', () => {
    mockedGetPatient.mockReturnValue(new Promise(() => {}))
    renderPage()

    expect(screen.getByRole('status')).toHaveTextContent('Loading patient')
  })

  it('fetches only this patient’s analyses, scoped by patientId', async () => {
    mockedListAnalyses.mockResolvedValue([])
    renderPage()

    await screen.findByRole('heading', { name: /Analyses for Jane Doe/ })
    expect(mockedListAnalyses).toHaveBeenCalledWith(7, 50)
  })

  it('shows a breadcrumb trail ending in Analyses', async () => {
    renderPage()

    const breadcrumb = await screen.findByRole('navigation', { name: 'Breadcrumb' })
    expect(within(breadcrumb).getByRole('link', { name: 'Jane Doe' })).toHaveAttribute(
      'href',
      '/patients/7',
    )
    expect(within(breadcrumb).getByText('Analyses')).toHaveAttribute('aria-current', 'page')
  })

  it('shows a back action to the patient overview and a link to start an analysis', async () => {
    mockedListAnalyses.mockResolvedValue([])
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: /Analyses for Jane Doe/ })
    expect(screen.getByRole('link', { name: '+ Start analysis' })).toHaveAttribute(
      'href',
      '/patients/7/upload',
    )

    await user.click(screen.getByRole('button', { name: 'Back to Jane Doe' }))
    expect(await screen.findByText('Patient Overview stub')).toBeInTheDocument()
  })

  it('shows the empty state with a link to start the first analysis', async () => {
    mockedListAnalyses.mockResolvedValue([])
    renderPage()

    expect(await screen.findByText('No analyses yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Start an analysis' })).toHaveAttribute(
      'href',
      '/patients/7/upload',
    )
  })

  it('lists this patient’s analyses, linking each to the patient-scoped detail route', async () => {
    mockedListAnalyses.mockResolvedValue([sampleAnalysis])
    renderPage()

    const cardLink = await screen.findByRole('link', { name: /status: Completed/ })
    expect(cardLink).toHaveAttribute('href', '/patients/7/analyses/42')
    expect(screen.getByText('Reconciliation completed with 1 finding.')).toBeInTheDocument()
  })

  it('deletes an analysis from the list', async () => {
    mockedListAnalyses.mockResolvedValue([sampleAnalysis])
    mockedDeleteAnalysis.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('Reconciliation completed with 1 finding.')
    await user.click(screen.getByRole('button', { name: /Delete analysis from/ }))

    await waitFor(() => expect(mockedDeleteAnalysis).toHaveBeenCalledWith(7, 42))
    expect(screen.queryByText('Reconciliation completed with 1 finding.')).not.toBeInTheDocument()
  })

  it('does not show a success notification on a normal visit', async () => {
    mockedListAnalyses.mockResolvedValue([])
    renderPage()

    await screen.findByRole('heading', { name: /Analyses for Jane Doe/ })
    expect(screen.queryByRole('button', { name: 'Dismiss notification' })).not.toBeInTheDocument()
    expect(screen.queryByText(/was deleted/)).not.toBeInTheDocument()
  })

  it('shows a temporary success notification after being navigated here with a flash message', async () => {
    mockedListAnalyses.mockResolvedValue([])
    renderPage({ flashMessage: 'Analysis #42 was deleted.' })

    expect(await screen.findByText('Analysis #42 was deleted.')).toBeInTheDocument()
  })

  it('dismisses the success notification when its close button is clicked', async () => {
    const user = userEvent.setup()
    mockedListAnalyses.mockResolvedValue([])
    renderPage({ flashMessage: 'Analysis #42 was deleted.' })

    await screen.findByText('Analysis #42 was deleted.')
    await user.click(screen.getByRole('button', { name: 'Dismiss notification' }))

    expect(screen.queryByText('Analysis #42 was deleted.')).not.toBeInTheDocument()
  })

  it('auto-dismisses the success notification after a short delay', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    mockedListAnalyses.mockResolvedValue([])
    renderPage({ flashMessage: 'Analysis #42 was deleted.' })

    expect(await screen.findByText('Analysis #42 was deleted.')).toBeInTheDocument()

    await vi.advanceTimersByTimeAsync(7000)

    await waitFor(() =>
      expect(screen.queryByText('Analysis #42 was deleted.')).not.toBeInTheDocument(),
    )
    vi.useRealTimers()
  })

  it('shows an error state for the analysis list independent of the patient details', async () => {
    mockedListAnalyses.mockRejectedValue({ status: 500, message: 'Could not load analyses.' })
    renderPage()

    await screen.findByRole('heading', { name: /Analyses for Jane Doe/ })
    expect(await screen.findByText('Could not load analyses.')).toBeInTheDocument()
  })

  it('shows a not-found error when the patient does not exist or is not owned by the user', async () => {
    mockedGetPatient.mockRejectedValue({ status: 404, message: 'Patient not found' })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Patient not found')
  })
})
