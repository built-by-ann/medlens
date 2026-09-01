import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AnalysisDetailPage } from '@/pages/AnalysisDetailPage'
import { getPatient } from '@/api/patients'
import { deleteAnalysis, getAnalysisDetail, resolveDiscrepancy } from '@/api/analyses'
import type {
  AnalysisDetail,
  AnalysisMedicationMention,
  MedicationDiscrepancy,
  Patient,
} from '@/types/api'

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
    deleteAnalysis: vi.fn(),
    resolveDiscrepancy: vi.fn(),
  }
})

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()

  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

const mockedGetPatient = vi.mocked(getPatient)
const mockedGetAnalysisDetail = vi.mocked(getAnalysisDetail)
const mockedDeleteAnalysis = vi.mocked(deleteAnalysis)
const mockedResolveDiscrepancy = vi.mocked(resolveDiscrepancy)

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
  document_count: 1,
  medication_mentions: [],
  possible_inconsistencies: [],
  medication_discrepancies: [],
}

function makeMedicationMention(
  overrides: Partial<AnalysisMedicationMention> = {},
): AnalysisMedicationMention {
  return {
    id: 1,
    medication_name: 'Lisinopril',
    dosage: '10 mg',
    route: 'oral',
    frequency: 'once daily',
    status: 'active',
    notes: null,
    ...overrides,
  }
}

function makeDiscrepancy(overrides: Partial<MedicationDiscrepancy> = {}): MedicationDiscrepancy {
  return {
    id: 1,
    analysis_id: 42,
    medication_id: null,
    medication_mention_id: null,
    discrepancy_type: 'missing_from_medication_list',
    severity: 'high',
    title: 'Lisinopril not found in medication list',
    ai_explanation:
      'Lisinopril is mentioned in the selected clinical documents but does not appear in the current medication list.',
    recommendation: null,
    expected_value: null,
    observed_value: 'Lisinopril',
    resolution_status: 'open',
    resolution_action: null,
    resolved_at: null,
    resolution_note: null,
    resolved_by: null,
    created_at: '2026-01-01T12:01:00Z',
    updated_at: null,
    medication: null,
    medication_mention: null,
    ...overrides,
  }
}

const withMentionEvidence = makeDiscrepancy({
  id: 1,
  medication_mention_id: 9,
  medication_mention: {
    id: 9,
    medication_name: 'Lisinopril',
    dose: '10 mg',
    route: 'oral',
    frequency: 'once daily',
    status: 'active',
    context_text: 'Patient takes Lisinopril 10mg oral daily.',
    clinical_document: {
      id: 3,
      title: 'March Visit Note',
      document_type: 'visit_note',
    },
  },
})

const withMedicationEvidence = makeDiscrepancy({
  id: 2,
  severity: 'low',
  discrepancy_type: 'unsupported_medication_list_entry',
  title: 'Warfarin not mentioned in selected documents',
  medication_id: 12,
  medication_mention_id: null,
  expected_value: 'Warfarin',
  observed_value: null,
  medication: {
    id: 12,
    patient_id: 7,
    medication_name: 'Warfarin',
    dose: '5 mg',
    route: 'oral',
    frequency: 'once daily',
    status: 'active',
    source: 'patient_reported',
    notes: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
  },
})

const withNoEvidence = makeDiscrepancy({
  id: 3,
  severity: 'medium',
  discrepancy_type: 'dose_conflict',
  title: 'A finding with no linked evidence',
  ai_explanation: 'This finding has no linked medication or medication mention.',
  observed_value: null,
})

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
    mockedDeleteAnalysis.mockReset()
    mockedResolveDiscrepancy.mockReset()
    mockNavigate.mockReset()
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
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Back to analyses' }))
    expect(mockNavigate).toHaveBeenCalledWith('/patients/7/analyses')
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

  it('shows a positive empty state when reconciliation found no discrepancies', async () => {
    renderPage()

    expect(
      await screen.findByText('No medication inconsistencies were detected.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('No medication inconsistencies')
  })

  it('shows summary counts that match the number of displayed findings', async () => {
    mockedGetAnalysisDetail.mockResolvedValue({
      ...completedAnalysis,
      medication_discrepancies: [withMentionEvidence, withMedicationEvidence, withNoEvidence],
    })
    renderPage()

    await screen.findByRole('heading', { name: 'Medication Reconciliation Findings' })

    const totalStat = screen.getByText('Total').closest('div') as HTMLElement
    expect(within(totalStat).getByText('3')).toBeInTheDocument()

    const highStat = screen.getByText('High').closest('div') as HTMLElement
    expect(within(highStat).getByText('1')).toBeInTheDocument()

    const mediumStat = screen.getByText('Medium').closest('div') as HTMLElement
    expect(within(mediumStat).getByText('1')).toBeInTheDocument()

    const lowStat = screen.getByText('Low').closest('div') as HTMLElement
    expect(within(lowStat).getByText('1')).toBeInTheDocument()
  })

  it('groups and sorts findings highest-severity-first', async () => {
    mockedGetAnalysisDetail.mockResolvedValue({
      ...completedAnalysis,
      medication_discrepancies: [withMedicationEvidence, withNoEvidence, withMentionEvidence],
    })
    renderPage()

    const findingsHeading = await screen.findByRole('heading', {
      name: 'Medication Reconciliation Findings',
    })
    const findingsSection = findingsHeading.closest('section') as HTMLElement

    const groupHeadings = within(findingsSection)
      .getAllByRole('heading', { level: 3 })
      .map((heading) => heading.textContent)
    expect(groupHeadings).toEqual(['High severity (1)', 'Medium severity (1)', 'Low severity (1)'])

    const medicationHeadings = screen
      .getAllByRole('heading', { level: 4 })
      .map((heading) => heading.textContent)
    expect(medicationHeadings).toEqual(['Lisinopril', 'Unknown medication', 'Warfarin'])
  })

  it('shows severity, discrepancy type, and resolution status on each card', async () => {
    mockedGetAnalysisDetail.mockResolvedValue({
      ...completedAnalysis,
      medication_discrepancies: [withMentionEvidence],
    })
    renderPage()

    await screen.findByRole('heading', { name: 'Lisinopril', level: 4 })
    expect(screen.getByText('High severity')).toBeInTheDocument()
    expect(screen.getByText('Missing from medication list')).toBeInTheDocument()
    expect(screen.getByText('Open')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Lisinopril is mentioned in the selected clinical documents but does not appear in the current medication list.',
      ),
    ).toBeInTheDocument()
  })

  it('shows supporting evidence with the source document and text snippet', async () => {
    mockedGetAnalysisDetail.mockResolvedValue({
      ...completedAnalysis,
      medication_discrepancies: [withMentionEvidence],
    })
    renderPage()

    await screen.findByRole('heading', { name: 'Lisinopril', level: 4 })
    expect(screen.getByText(/Source: March Visit Note/)).toBeInTheDocument()
    expect(
      screen.getByText('“Patient takes Lisinopril 10mg oral daily.”', { exact: false }),
    ).toBeInTheDocument()
  })

  it('shows medication-list evidence when there is no mention', async () => {
    mockedGetAnalysisDetail.mockResolvedValue({
      ...completedAnalysis,
      medication_discrepancies: [withMedicationEvidence],
    })
    renderPage()

    await screen.findByRole('heading', { name: 'Warfarin', level: 4 })
    expect(screen.getByText(/Currently on the medication list: Warfarin/)).toBeInTheDocument()
  })

  it('explains when a finding has no supporting evidence', async () => {
    mockedGetAnalysisDetail.mockResolvedValue({
      ...completedAnalysis,
      medication_discrepancies: [withNoEvidence],
    })
    renderPage()

    await screen.findByRole('heading', { name: 'Unknown medication', level: 4 })
    expect(
      screen.getByText('No supporting evidence was recorded for this finding.'),
    ).toBeInTheDocument()
  })

  it('uses a sane, non-skipping heading hierarchy', async () => {
    mockedGetAnalysisDetail.mockResolvedValue({
      ...completedAnalysis,
      medication_discrepancies: [withMentionEvidence],
    })
    renderPage()

    await screen.findByRole('heading', { name: 'Analysis #42', level: 1 })
    expect(screen.getByRole('heading', { name: 'AI Summary', level: 2 })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Summary', level: 3 })).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Medication Reconciliation Findings', level: 2 }),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'High severity (1)', level: 3 })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Lisinopril', level: 4 })).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Supporting evidence', level: 5 }),
    ).toBeInTheDocument()
  })

  it('visually distinguishes the AI Summary section from the deterministic findings section', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'AI Summary' })
    expect(screen.getByText('AI-generated')).toBeInTheDocument()
    expect(screen.getByText('Deterministic')).toBeInTheDocument()
  })

  it('shows a helpful empty state when no AI summary is available, without hiding reconciliation findings', async () => {
    mockedGetAnalysisDetail.mockResolvedValue({
      ...completedAnalysis,
      summary: null,
      medication_discrepancies: [withMentionEvidence],
    })
    renderPage()

    expect(
      await screen.findByText('No AI summary is available for this analysis.'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Medication Reconciliation Findings' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Lisinopril', level: 4 })).toBeInTheDocument()
  })

  it('shows medications mentioned by the AI when present', async () => {
    mockedGetAnalysisDetail.mockResolvedValue({
      ...completedAnalysis,
      medication_mentions: [
        makeMedicationMention({ id: 5, medication_name: 'Metformin', dosage: '500 mg' }),
      ],
    })
    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'Medications Mentioned' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Metformin')).toBeInTheDocument()
    expect(screen.getByText(/500 mg/)).toBeInTheDocument()
  })

  it('omits the Medications Mentioned section entirely when there are none', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'AI Summary' })
    expect(screen.queryByRole('heading', { name: 'Medications Mentioned' })).not.toBeInTheDocument()
  })

  it('shows summary metadata including provider, model, and document count', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'Summary Metadata' })
    expect(screen.getByText('gemini')).toBeInTheDocument()
    expect(screen.getByText('gemini-2.0-flash')).toBeInTheDocument()

    const documentCountStat = screen.getByText('Documents analyzed').closest('div') as HTMLElement
    expect(within(documentCountStat).getByText('1')).toBeInTheDocument()
  })

  it('shows a visible Delete analysis action alongside the status badge', async () => {
    renderPage()

    expect(await screen.findByRole('button', { name: 'Delete analysis' })).toBeInTheDocument()
  })

  it('opens a confirmation dialog naming the analysis and patient with a permanent-deletion warning', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Delete analysis' }))

    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText('Delete this analysis?')).toBeInTheDocument()
    expect(within(dialog).getByText('Analysis #42 for Jane Doe')).toBeInTheDocument()
    expect(within(dialog).getByText(/cannot be undone/)).toBeInTheDocument()
    expect(mockedDeleteAnalysis).not.toHaveBeenCalled()
  })

  it('places initial focus on Cancel, the safest action', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Delete analysis' }))

    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus()
  })

  it('closes the dialog without deleting when Cancel is clicked', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Delete analysis' }))
    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(mockedDeleteAnalysis).not.toHaveBeenCalled()
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('dismisses the dialog with the Escape key, without deleting', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Delete analysis' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    await user.keyboard('{Escape}')

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(mockedDeleteAnalysis).not.toHaveBeenCalled()
  })

  it('deletes the analysis and navigates back to the patient analyses page with a success message', async () => {
    const user = userEvent.setup()
    mockedDeleteAnalysis.mockResolvedValue(undefined)
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Delete analysis' }))
    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Delete analysis' }))

    await waitFor(() => expect(mockedDeleteAnalysis).toHaveBeenCalledWith(7, 42))
    expect(mockNavigate).toHaveBeenCalledWith('/patients/7/analyses', {
      state: { flashMessage: 'Analysis #42 was deleted.' },
    })
  })

  it('shows a loading state while deleting and prevents duplicate submissions', async () => {
    const user = userEvent.setup()
    let resolveDelete: () => void = () => {}
    mockedDeleteAnalysis.mockReturnValue(
      new Promise((resolve) => {
        resolveDelete = () => resolve(undefined)
      }),
    )
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Delete analysis' }))
    const dialog = screen.getByRole('dialog')
    const confirmButton = within(dialog).getByRole('button', { name: 'Delete analysis' })

    await user.click(confirmButton)
    expect(await within(dialog).findByRole('button', { name: 'Deleting...' })).toBeDisabled()
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toBeDisabled()

    await user.click(within(dialog).getByRole('button', { name: 'Deleting...' }))
    expect(mockedDeleteAnalysis).toHaveBeenCalledTimes(1)

    resolveDelete()
    await waitFor(() => expect(mockNavigate).toHaveBeenCalled())
  })

  it('shows an error inside the dialog and keeps the user on the page when deletion fails', async () => {
    const user = userEvent.setup()
    mockedDeleteAnalysis.mockRejectedValue({ status: 500, message: 'Could not delete analysis.' })
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Delete analysis' }))
    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Delete analysis' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Could not delete analysis.')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(mockNavigate).not.toHaveBeenCalled()

    // Allows retry: the confirm button is re-enabled after the failure.
    expect(within(dialog).getByRole('button', { name: 'Delete analysis' })).toBeEnabled()
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

  describe('resolving a discrepancy', () => {
    beforeEach(() => {
      mockedGetAnalysisDetail.mockResolvedValue({
        ...completedAnalysis,
        medication_discrepancies: [withMentionEvidence],
      })
    })

    it('opens the resolve dialog naming the chosen action and medication', async () => {
      const user = userEvent.setup()
      renderPage()

      await user.click(await screen.findByRole('button', { name: /Add Medication/ }))

      expect(screen.getByRole('dialog', { name: 'Add Medication: Lisinopril' })).toBeInTheDocument()
    })

    it('accepting a medication addition calls the API, applies the update, and shows success feedback', async () => {
      const user = userEvent.setup()
      const resolved = {
        ...withMentionEvidence,
        resolution_status: 'resolved' as const,
        resolution_action: 'add_medication' as const,
        resolved_at: '2026-01-02T09:00:00Z',
        medication_id: 55,
      }
      mockedResolveDiscrepancy.mockResolvedValue(resolved)
      renderPage()

      await user.click(await screen.findByRole('button', { name: /Add Medication/ }))
      const dialog = screen.getByRole('dialog')
      await user.click(within(dialog).getByRole('button', { name: 'Confirm' }))

      await waitFor(() =>
        expect(mockedResolveDiscrepancy).toHaveBeenCalledWith(7, 42, withMentionEvidence.id, {
          action: 'add_medication',
          medication_name: 'Lisinopril',
          dose: '10 mg',
          route: 'oral',
          frequency: 'once daily',
          status: 'active',
        }),
      )

      // The dialog closes, a status announcement appears, and the card no
      // longer offers actions for an already-resolved discrepancy.
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(await screen.findByRole('status')).toHaveTextContent(
        'Updated the medication list for Lisinopril.',
      )
      expect(screen.queryByRole('button', { name: /Add Medication/ })).not.toBeInTheDocument()
    })

    it('dismissing a discrepancy shows dismissal-specific success feedback', async () => {
      const user = userEvent.setup()
      mockedResolveDiscrepancy.mockResolvedValue({
        ...withMentionEvidence,
        resolution_status: 'dismissed',
        resolution_action: 'dismiss',
        resolved_at: '2026-01-02T09:00:00Z',
      })
      renderPage()

      await user.click(await screen.findByRole('button', { name: /^Dismiss/ }))
      const dialog = screen.getByRole('dialog')
      await user.click(within(dialog).getByRole('button', { name: 'Confirm' }))

      expect(await screen.findByRole('status')).toHaveTextContent(
        'Dismissed the finding for Lisinopril.',
      )
    })

    it('shows an error inside the dialog and leaves the discrepancy open when resolution fails', async () => {
      const user = userEvent.setup()
      mockedResolveDiscrepancy.mockRejectedValue({
        status: 409,
        message: 'Discrepancy has already been resolved',
      })
      renderPage()

      await user.click(await screen.findByRole('button', { name: /^Dismiss/ }))
      const dialog = screen.getByRole('dialog')
      await user.click(within(dialog).getByRole('button', { name: 'Confirm' }))

      expect(await within(dialog).findByRole('alert')).toHaveTextContent(
        'Discrepancy has already been resolved',
      )
      expect(screen.getByRole('dialog')).toBeInTheDocument()
      // Still open; the action buttons are still there to retry.
      expect(screen.getByRole('button', { name: /^Dismiss/ })).toBeInTheDocument()
    })

    it('closes the dialog without resolving when Cancel is clicked', async () => {
      const user = userEvent.setup()
      renderPage()

      await user.click(await screen.findByRole('button', { name: /^Dismiss/ }))
      await user.click(screen.getByRole('button', { name: 'Cancel' }))

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(mockedResolveDiscrepancy).not.toHaveBeenCalled()
    })

    it('resolving one discrepancy leaves a second, unrelated discrepancy untouched', async () => {
      const user = userEvent.setup()
      const doseConflict = makeDiscrepancy({
        id: 2,
        discrepancy_type: 'dose_conflict',
        medication_id: 5,
        medication: {
          id: 5,
          patient_id: 7,
          medication_name: 'Metformin',
          dose: '250 mg',
          route: 'oral',
          frequency: 'twice daily',
          status: 'active',
          source: 'patient_reported',
          notes: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: null,
        },
        medication_mention_id: 10,
        medication_mention: {
          id: 10,
          medication_name: 'Metformin',
          dose: '500 mg',
          route: 'oral',
          frequency: 'twice daily',
          status: 'active',
          context_text: null,
          clinical_document: { id: 3, title: 'Visit Note', document_type: 'visit_note' },
        },
      })
      mockedGetAnalysisDetail.mockResolvedValue({
        ...completedAnalysis,
        medication_discrepancies: [withMentionEvidence, doseConflict],
      })
      mockedResolveDiscrepancy.mockResolvedValue({
        ...withMentionEvidence,
        resolution_status: 'dismissed',
        resolution_action: 'dismiss',
        resolved_at: '2026-01-02T09:00:00Z',
      })
      renderPage()

      await user.click(await screen.findByRole('button', { name: 'Dismiss: Lisinopril' }))
      const dialog = screen.getByRole('dialog')
      await user.click(within(dialog).getByRole('button', { name: 'Confirm' }))

      await waitFor(() =>
        expect(
          screen.queryByRole('button', { name: 'Dismiss: Lisinopril' }),
        ).not.toBeInTheDocument(),
      )
      // Metformin's dose_conflict was never touched; still open, still actionable.
      expect(
        screen.getByRole('button', { name: /Update Medication: Metformin/ }),
      ).toBeInTheDocument()
    })
  })
})
