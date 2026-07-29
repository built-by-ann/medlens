import { render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AnalysisDetailPage } from '@/pages/AnalysisDetailPage'
import { getPatient } from '@/api/patients'
import { getAnalysisDetail } from '@/api/analyses'
import type { AnalysisDetail, MedicationDiscrepancy, Patient } from '@/types/api'

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

const doseConflictFinding: MedicationDiscrepancy = {
  id: 1,
  analysis_id: 42,
  medication_id: 5,
  medication_mention_id: 9,
  discrepancy_type: 'dose_conflict',
  severity: 'medium',
  title: 'Lisinopril dose does not match',
  ai_explanation: 'The medication list records 10 mg but a document records 20 mg.',
  recommendation: 'Confirm the correct dose with the patient.',
  expected_value: '10 mg',
  observed_value: '20 mg',
  resolution_status: 'open',
  created_at: '2026-01-01T12:01:00Z',
  updated_at: null,
  medication: {
    id: 5,
    patient_id: 7,
    medication_name: 'Lisinopril',
    dose: '10 mg',
    route: 'oral',
    frequency: 'once daily',
    status: 'active',
    source: 'patient_reported',
    notes: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
  },
  medication_mention: {
    id: 9,
    medication_name: 'Lisinopril',
    dose: '20 mg',
    route: 'oral',
    frequency: 'once daily',
    status: 'active',
    context_text: 'Patient takes Lisinopril 20mg oral daily.',
    clinical_document: {
      id: 3,
      title: 'March Visit Note',
      document_type: 'visit_note',
    },
  },
}

const missingFromListFinding: MedicationDiscrepancy = {
  id: 2,
  analysis_id: 42,
  medication_id: null,
  medication_mention_id: 11,
  discrepancy_type: 'missing_from_medication_list',
  severity: 'high',
  title: 'Metformin not found in medication list',
  ai_explanation: null,
  recommendation: null,
  expected_value: null,
  observed_value: null,
  resolution_status: 'open',
  created_at: '2026-01-01T12:02:00Z',
  updated_at: null,
  medication: null,
  medication_mention: {
    id: 11,
    medication_name: 'Metformin',
    dose: '500 mg',
    route: 'oral',
    frequency: 'twice daily',
    status: 'active',
    context_text: 'Patient reports taking Metformin 500mg twice daily.',
    clinical_document: {
      id: 4,
      title: 'Discharge Summary',
      document_type: 'discharge_summary',
    },
  },
}

const noEvidenceFinding: MedicationDiscrepancy = {
  id: 3,
  analysis_id: 42,
  medication_id: null,
  medication_mention_id: null,
  discrepancy_type: 'dose_conflict',
  severity: 'low',
  title: 'Some finding with no linked evidence',
  ai_explanation: null,
  recommendation: null,
  expected_value: null,
  observed_value: null,
  resolution_status: 'dismissed',
  created_at: '2026-01-01T12:03:00Z',
  updated_at: null,
  medication: null,
  medication_mention: null,
}

const completedAnalysis: AnalysisDetail = {
  id: 42,
  patient_id: 7,
  status: 'completed',
  provider: 'gemini',
  model_name: 'gemini-2.0-flash',
  summary: 'Reconciliation completed with 2 findings.',
  started_at: '2026-01-01T12:00:00Z',
  completed_at: '2026-01-01T12:00:45Z',
  error_message: null,
  created_at: '2026-01-01T11:59:00Z',
  updated_at: '2026-01-01T12:00:45Z',
  document_count: 2,
  medication_mentions: [
    {
      id: 9,
      medication_name: 'Lisinopril',
      dosage: '20 mg',
      route: 'oral',
      frequency: 'once daily',
      status: 'active',
      notes: null,
    },
  ],
  possible_inconsistencies: [],
  medication_discrepancies: [doseConflictFinding, missingFromListFinding],
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

    await screen.findByRole('heading', { name: 'Analysis Results', level: 1 })
    expect(mockedGetAnalysisDetail).toHaveBeenCalledWith(7, 42)
  })

  it('shows the page title, analysis id, patient name, and completion status', async () => {
    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'Analysis Results', level: 1 }),
    ).toBeInTheDocument()
    expect(screen.getByText('Analysis #42 for Jane Doe')).toBeInTheDocument()
    expect(screen.getByText('Completed', { selector: 'span' })).toBeInTheDocument()
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

  it('links to Patient Overview, Analysis History, and Clinical Documents', async () => {
    renderPage()

    const nav = await screen.findByRole('navigation', { name: 'Analysis navigation' })
    expect(within(nav).getByRole('link', { name: /Patient Overview/ })).toHaveAttribute(
      'href',
      '/patients/7',
    )
    expect(within(nav).getByRole('link', { name: 'Analysis History' })).toHaveAttribute(
      'href',
      '/patients/7/analyses',
    )
    expect(within(nav).getByRole('link', { name: 'Clinical Documents' })).toHaveAttribute(
      'href',
      '/patients/7#documents-heading',
    )
  })

  it('shows the Patient Information section with patient demographics', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'Patient Information' })
    expect(screen.getByText('Date of birth')).toBeInTheDocument()
    expect(screen.getByText('Status')).toBeInTheDocument()
  })

  it('shows the AI summary and counts in the Analysis Summary section', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'Analysis Summary' })
    expect(screen.getByText('Reconciliation completed with 2 findings.')).toBeInTheDocument()

    const discrepanciesStat = screen.getByText('Discrepancies found').closest('div') as HTMLElement
    expect(within(discrepanciesStat).getByText('2')).toBeInTheDocument()

    const medicationsStat = screen.getByText('Medications analyzed').closest('div') as HTMLElement
    expect(within(medicationsStat).getByText('1')).toBeInTheDocument()

    const documentsStat = screen.getByText('Documents analyzed').closest('div') as HTMLElement
    expect(within(documentsStat).getByText('2')).toBeInTheDocument()
  })

  it('shows a placeholder when no AI summary was generated', async () => {
    mockedGetAnalysisDetail.mockResolvedValue({ ...completedAnalysis, summary: null })
    renderPage()

    expect(
      await screen.findByText('No AI summary was generated for this analysis.'),
    ).toBeInTheDocument()
  })

  it('renders every reconciliation finding with severity, medication, type, status, and description', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'Medication Reconciliation Findings' })

    expect(screen.getByRole('heading', { name: 'Lisinopril', level: 3 })).toBeInTheDocument()
    expect(screen.getByText('Dose conflict')).toBeInTheDocument()
    expect(screen.getByText('Medium severity')).toBeInTheDocument()
    expect(screen.getAllByText('Open').length).toBeGreaterThan(0)
    expect(
      screen.getByText('The medication list records 10 mg but a document records 20 mg.'),
    ).toBeInTheDocument()

    expect(screen.getByRole('heading', { name: 'Metformin', level: 3 })).toBeInTheDocument()
    expect(screen.getByText('Missing from medication list')).toBeInTheDocument()
    expect(screen.getByText('High severity')).toBeInTheDocument()
  })

  it('sorts findings by severity, highest first', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'Medication Reconciliation Findings' })
    const headings = screen.getAllByRole('heading', { level: 3 }).map((el) => el.textContent)

    expect(headings).toEqual(['Metformin', 'Lisinopril'])
  })

  it('shows supporting evidence with the source document and text snippet', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'Medication Reconciliation Findings' })
    expect(screen.getByText(/Source: March Visit Note/)).toBeInTheDocument()
    expect(
      screen.getByText('“Patient takes Lisinopril 20mg oral daily.”', { exact: false }),
    ).toBeInTheDocument()
  })

  it('explains when a finding has no supporting evidence, falling back to its title as the heading', async () => {
    mockedGetAnalysisDetail.mockResolvedValue({
      ...completedAnalysis,
      medication_discrepancies: [noEvidenceFinding],
    })
    renderPage()

    await screen.findByRole('heading', { name: 'Medication Reconciliation Findings' })
    expect(
      screen.getByText('No supporting evidence was recorded for this finding.'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Unknown medication', level: 3 }),
    ).toBeInTheDocument()
  })

  it('shows an empty state explaining that no findings are available', async () => {
    mockedGetAnalysisDetail.mockResolvedValue({
      ...completedAnalysis,
      medication_discrepancies: [],
    })
    renderPage()

    expect(
      await screen.findByText(
        'No medication reconciliation findings are available for this analysis.',
      ),
    ).toBeInTheDocument()
  })

  it('shows analysis id, timestamps, provider, model, and processing duration in metadata', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'Analysis Metadata' })
    expect(screen.getByText('Analysis ID')).toBeInTheDocument()
    expect(screen.getByText('42', { selector: 'dd' })).toBeInTheDocument()
    expect(screen.getByText('Provider')).toBeInTheDocument()
    expect(screen.getByText('gemini')).toBeInTheDocument()
    expect(screen.getByText('gemini-2.0-flash')).toBeInTheDocument()
    expect(screen.getByText('Processing duration')).toBeInTheDocument()
    expect(screen.getByText('45s')).toBeInTheDocument()
  })

  it('omits processing duration when timestamps are not both available', async () => {
    mockedGetAnalysisDetail.mockResolvedValue({ ...completedAnalysis, started_at: null })
    renderPage()

    await screen.findByRole('heading', { name: 'Analysis Metadata' })
    expect(screen.queryByText('Processing duration')).not.toBeInTheDocument()
  })

  it('shows the sanitized error message for a failed analysis', async () => {
    mockedGetAnalysisDetail.mockResolvedValue({
      ...completedAnalysis,
      status: 'failed',
      summary: null,
      provider: null,
      model_name: null,
      medication_discrepancies: [],
      completed_at: '2026-01-01T12:05:00Z',
      error_message: 'Gemini API key is not configured',
    })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Gemini API key is not configured')
    expect(screen.getByText('Failed')).toBeInTheDocument()
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

  it('uses a single h1 and section-level h2 headings for a sane heading hierarchy', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'Analysis Metadata' })

    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    const h2s = screen.getAllByRole('heading', { level: 2 }).map((el) => el.textContent)
    expect(h2s).toEqual([
      'Patient Information',
      'Analysis Summary',
      'Medication Reconciliation Findings',
      'Analysis Metadata',
    ])
  })
})
