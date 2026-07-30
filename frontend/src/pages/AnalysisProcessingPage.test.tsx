import { StrictMode } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AnalysisProcessingPage } from '@/pages/AnalysisProcessingPage'
import { useCreateAnalysis, type SubmitInput } from '@/hooks/useCreateAnalysis'
import { useAnalysisPolling } from '@/hooks/useAnalysisPolling'
import { getPatient } from '@/api/patients'
import type { AnalysisDetail, Patient } from '@/types/api'

vi.mock('@/hooks/useCreateAnalysis', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/hooks/useCreateAnalysis')>()

  return {
    ...actual,
    useCreateAnalysis: vi.fn(),
  }
})

vi.mock('@/hooks/useAnalysisPolling', () => ({
  useAnalysisPolling: vi.fn(),
}))

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    getPatient: vi.fn(),
  }
})

const mockedUseCreateAnalysis = vi.mocked(useCreateAnalysis)
const mockedUseAnalysisPolling = vi.mocked(useAnalysisPolling)
const mockedGetPatient = vi.mocked(getPatient)

const submit = vi.fn()
const invalidateItem = vi.fn()
const saveDocuments = vi.fn()

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

const submission: SubmitInput = {
  files: [],
  notes: [{ id: 0, title: '', rawText: 'Some note text', documentType: 'visit_note' }],
}

function makeAnalysis(overrides: Partial<AnalysisDetail> = {}): AnalysisDetail {
  return {
    id: 99,
    patient_id: 7,
    status: 'processing',
    provider: null,
    model_name: null,
    summary: null,
    started_at: null,
    completed_at: null,
    error_message: null,
    created_at: '2026-01-01T12:00:00Z',
    updated_at: null,
    document_count: 1,
    medication_mentions: [],
    possible_inconsistencies: [],
    medication_discrepancies: [],
    ...overrides,
  }
}

function renderProcessingPage(state: SubmitInput | null = submission, { strict = false } = {}) {
  const tree = (
    <MemoryRouter initialEntries={[{ pathname: '/patients/7/analyses/processing', state }]}>
      <Routes>
        <Route
          path="/patients/:patientId/analyses/processing"
          element={<AnalysisProcessingPage />}
        />
        <Route
          path="/patients/:patientId/analyses/:analysisId"
          element={<div data-testid="results-probe">Analysis results</div>}
        />
        <Route path="/patients/:patientId/upload" element={<div>Upload page</div>} />
        <Route path="/patients/:patientId" element={<div>Patient overview</div>} />
        <Route path="/patients/:patientId/analyses" element={<div>Analysis history</div>} />
      </Routes>
    </MemoryRouter>
  )

  return render(strict ? <StrictMode>{tree}</StrictMode> : tree)
}

describe('AnalysisProcessingPage', () => {
  beforeEach(() => {
    submit.mockReset()
    invalidateItem.mockReset()
    saveDocuments.mockReset()
    mockedGetPatient.mockReset()
    mockedGetPatient.mockResolvedValue(patient)
    mockedUseCreateAnalysis.mockReturnValue({
      isSubmitting: false,
      error: null,
      failedItemLabel: null,
      submit,
      saveDocuments,
      invalidateItem,
    })
    mockedUseAnalysisPolling.mockReturnValue({ analysis: null, error: null })
  })

  it('shows a loading state while the patient is being fetched', () => {
    mockedGetPatient.mockReturnValue(new Promise(() => {}))
    submit.mockReturnValue(new Promise(() => {}))
    renderProcessingPage()

    expect(screen.getByText('Loading patient')).toBeInTheDocument()
  })

  it('shows a recovery card when there is no queued submission (direct visit or refresh)', async () => {
    renderProcessingPage(null)

    expect(await screen.findByRole('heading', { name: 'Nothing to process' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Go to Upload' })).toHaveAttribute(
      'href',
      '/patients/7/upload',
    )
    expect(submit).not.toHaveBeenCalled()
  })

  it('submits the queued files and notes as soon as the page mounts', async () => {
    submit.mockReturnValue(new Promise(() => {}))
    renderProcessingPage()

    await waitFor(() => expect(submit).toHaveBeenCalledWith(submission))
  })

  it("submits only once even under React Strict Mode's dev-only double-invoked mount effects", async () => {
    // Regression test: Strict Mode double-invoking the unguarded mount
    // effect used to run the real upload-and-create-analysis sequence
    // twice, producing a duplicate ClinicalDocument and a duplicate
    // Analysis. The hasStartedSubmissionRef guard must prevent that.
    submit.mockReturnValue(new Promise(() => {}))
    renderProcessingPage(submission, { strict: true })

    await waitFor(() => expect(submit).toHaveBeenCalled())
    expect(submit).toHaveBeenCalledTimes(1)
  })

  it('shows the processing experience with rotating progress messaging while submitting', async () => {
    submit.mockReturnValue(new Promise(() => {}))
    mockedUseCreateAnalysis.mockReturnValue({
      isSubmitting: true,
      error: null,
      failedItemLabel: null,
      submit,
      saveDocuments,
      invalidateItem,
    })
    renderProcessingPage()

    await screen.findByRole('heading', { name: 'Analysis Processing' })
    expect(screen.getByText('Preparing analysis...')).toBeInTheDocument()
    expect(screen.getByText('AI is reviewing uploaded clinical documents.')).toBeInTheDocument()
    expect(screen.getByText(/Estimated time/)).toBeInTheDocument()
    expect(screen.getByText('Please keep this page open.')).toBeInTheDocument()
  })

  it('shows analysis metadata once polling returns a non-terminal analysis', async () => {
    submit.mockResolvedValue(99)
    mockedUseAnalysisPolling.mockReturnValue({
      analysis: makeAnalysis({ status: 'processing' }),
      error: null,
    })
    const { container } = renderProcessingPage()

    await screen.findByText('Created')
    expect(container.querySelector('.bg-blue-100')).toHaveTextContent('Processing')
  })

  it('automatically navigates to the analysis results page once completed', async () => {
    submit.mockResolvedValue(99)
    mockedUseAnalysisPolling.mockReturnValue({
      analysis: makeAnalysis({ id: 99, status: 'completed' }),
      error: null,
    })
    renderProcessingPage()

    expect(await screen.findByTestId('results-probe')).toBeInTheDocument()
  })

  it('shows a failure state with a retry option when submission itself fails', async () => {
    submit.mockRejectedValueOnce(new Error('failed'))
    mockedUseCreateAnalysis.mockReturnValue({
      isSubmitting: false,
      error: 'Something went wrong on the server.',
      failedItemLabel: 'note',
      submit,
      saveDocuments,
      invalidateItem,
    })
    const user = userEvent.setup()
    renderProcessingPage()

    expect(await screen.findByRole('heading', { name: 'Analysis failed' })).toBeInTheDocument()
    expect(screen.getByText('Something went wrong on the server.')).toBeInTheDocument()

    const retryButton = screen.getByRole('button', { name: 'Try again' })
    await user.click(retryButton)
    expect(submit).toHaveBeenCalledTimes(2)

    expect(screen.getByRole('link', { name: 'Return to Patient Overview' })).toHaveAttribute(
      'href',
      '/patients/7',
    )
    expect(screen.getByRole('link', { name: 'Return to Analysis History' })).toHaveAttribute(
      'href',
      '/patients/7/analyses',
    )
  })

  it('shows a failure state when the analysis itself reaches a failed status', async () => {
    submit.mockResolvedValue(99)
    mockedUseAnalysisPolling.mockReturnValue({
      analysis: makeAnalysis({ status: 'failed', error_message: 'The AI provider timed out.' }),
      error: null,
    })
    renderProcessingPage()

    expect(await screen.findByRole('heading', { name: 'Analysis failed' })).toBeInTheDocument()
    expect(screen.getByText('The AI provider timed out.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('shows a failure state without a retry option when only the status check fails', async () => {
    submit.mockResolvedValue(99)
    mockedUseAnalysisPolling.mockReturnValue({
      analysis: null,
      error: 'Network error.',
    })
    renderProcessingPage()

    expect(await screen.findByRole('heading', { name: 'Analysis failed' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Return to Analysis History' })).toBeInTheDocument()
  })
})
