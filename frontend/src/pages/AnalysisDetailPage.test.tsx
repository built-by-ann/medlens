import { render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AnalysisDetailPage } from '@/pages/AnalysisDetailPage'
import { getPatient } from '@/api/patients'
import { getAnalysisDetail } from '@/api/analyses'
import type { AnalysisDetail, Patient } from '@/types/api'

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
    getAnalysisDetail: vi.fn(),
  }
})

const mockedGetPatient = vi.mocked(getPatient)
const mockedGetAnalysisDetail = vi.mocked(getAnalysisDetail)

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

const completedAnalysis: AnalysisDetail = {
  id: 42,
  patient_id: 7,
  status: 'completed',
  provider: 'gemini',
  model_name: 'gemini-2.0-flash',
  summary: 'Reconciliation completed with 1 finding.',
  started_at: '2026-01-01T12:00:00Z',
  completed_at: '2026-01-01T12:05:00Z',
  error_message: null,
  created_at: '2026-01-01T11:59:00Z',
  updated_at: '2026-01-01T12:05:00Z',
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/patients/7/analyses/42']}>
      <Routes>
        <Route path="/patients/:patientId/analyses/:analysisId" element={<AnalysisDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AnalysisDetailPage', () => {
  beforeEach(() => {
    mockedGetPatient.mockReset()
    mockedGetAnalysisDetail.mockReset()
    mockedGetPatient.mockResolvedValue(patient)
    mockedGetAnalysisDetail.mockResolvedValue(completedAnalysis)
  })

  it('shows a loading state while the patient and analysis are being fetched', () => {
    mockedGetAnalysisDetail.mockReturnValue(new Promise(() => {}))
    renderPage()

    expect(screen.getByRole('status')).toHaveTextContent('Loading analysis')
  })

  it('fetches the analysis scoped to the patient and analysis ids in the route', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'Analysis #42' })
    expect(mockedGetAnalysisDetail).toHaveBeenCalledWith(7, 42)
  })

  it('shows the analysis id and patient name in the heading', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Analysis #42' })).toBeInTheDocument()
    expect(screen.getByText('For Jane Doe')).toBeInTheDocument()
  })

  it('shows a breadcrumb trail through Analyses to this analysis', async () => {
    renderPage()

    const breadcrumb = await screen.findByRole('navigation', { name: 'Breadcrumb' })
    expect(within(breadcrumb).getByRole('link', { name: 'Jane Doe' })).toHaveAttribute(
      'href',
      '/patients/7',
    )
    expect(within(breadcrumb).getByRole('link', { name: 'Analyses' })).toHaveAttribute(
      'href',
      '/patients/7/analyses',
    )
    expect(within(breadcrumb).getByText('Analysis #42')).toHaveAttribute('aria-current', 'page')
  })

  it('links back to this patient’s analysis history', async () => {
    renderPage()

    expect(await screen.findByRole('link', { name: /Back to analyses/ })).toHaveAttribute(
      'href',
      '/patients/7/analyses',
    )
  })

  it('shows the status badge, summary, provider, model, and timestamps', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'Analysis #42' })
    expect(screen.getByText('Completed', { selector: 'span' })).toBeInTheDocument()
    expect(screen.getByText('Reconciliation completed with 1 finding.')).toBeInTheDocument()
    expect(screen.getByText('gemini')).toBeInTheDocument()
    expect(screen.getByText('gemini-2.0-flash')).toBeInTheDocument()
  })

  it('shows the sanitized error message for a failed analysis', async () => {
    mockedGetAnalysisDetail.mockResolvedValue({
      ...completedAnalysis,
      status: 'failed',
      summary: null,
      provider: null,
      model_name: null,
      completed_at: '2026-01-01T12:05:00Z',
      error_message: 'Gemini API key is not configured',
    })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Gemini API key is not configured')
    expect(screen.getByText('Failed')).toBeInTheDocument()
  })

  it('shows a placeholder for the not-yet-built findings UI', async () => {
    renderPage()

    expect(
      await screen.findByText(/Detailed medication findings and inconsistency detection/),
    ).toBeInTheDocument()
  })

  it('shows a not-found error when the analysis does not exist or is not owned by the patient', async () => {
    mockedGetAnalysisDetail.mockRejectedValue({ status: 404, message: 'Analysis not found' })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Analysis not found')
  })

  it('shows a not-found error when the patient does not exist or is not owned by the user', async () => {
    mockedGetPatient.mockRejectedValue({ status: 404, message: 'Patient not found' })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Patient not found')
  })
})
