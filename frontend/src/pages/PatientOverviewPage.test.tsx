import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PatientOverviewPage } from '@/pages/PatientOverviewPage'
import { archivePatient, getPatient } from '@/api/patients'
import { deleteMedication, listMedications, updateMedication } from '@/api/medications'
import { listClinicalDocuments } from '@/api/clinicalDocuments'
import { deleteAnalysis, listAnalyses } from '@/api/analyses'
import type { AnalysisSummary, ClinicalDocument, Medication, Patient } from '@/types/api'

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    getPatient: vi.fn(),
    archivePatient: vi.fn(),
  }
})

vi.mock('@/api/medications', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/medications')>()

  return {
    ...actual,
    listMedications: vi.fn(),
    updateMedication: vi.fn(),
    deleteMedication: vi.fn(),
  }
})

vi.mock('@/api/clinicalDocuments', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/clinicalDocuments')>()

  return {
    ...actual,
    listClinicalDocuments: vi.fn(),
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
const mockedArchivePatient = vi.mocked(archivePatient)
const mockedListMedications = vi.mocked(listMedications)
const mockedUpdateMedication = vi.mocked(updateMedication)
const mockedDeleteMedication = vi.mocked(deleteMedication)
const mockedListClinicalDocuments = vi.mocked(listClinicalDocuments)
const mockedListAnalyses = vi.mocked(listAnalyses)
const mockedDeleteAnalysis = vi.mocked(deleteAnalysis)
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

const sampleMedication: Medication = {
  id: 5,
  patient_id: 1,
  medication_name: 'Lisinopril',
  dose: '10 mg',
  route: 'oral',
  frequency: 'once daily',
  status: 'active',
  source: 'patient_reported',
  notes: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
}

function makeDocument(overrides: Partial<ClinicalDocument> = {}): ClinicalDocument {
  return {
    id: 9,
    patient_id: 1,
    document_type: 'visit_note',
    title: 'Initial Visit',
    raw_text: 'Patient presents with hypertension.',
    file_name: null,
    file_type: 'manual_entry',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    analysis_count: 0,
    ...overrides,
  }
}

const sampleDocument: ClinicalDocument = makeDocument()

const sampleAnalysis: AnalysisSummary = {
  id: 42,
  patient_id: 1,
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
  open_findings: 0,
  provider: 'gemini',
  model_name: 'gemini-2.0-flash',
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
    mockedListMedications.mockReset()
    mockedUpdateMedication.mockReset()
    mockedDeleteMedication.mockReset()
    mockedListClinicalDocuments.mockReset()
    mockedListAnalyses.mockReset()
    mockedDeleteAnalysis.mockReset()
    mockNavigate.mockReset()
    mockedListMedications.mockResolvedValue([])
    mockedListClinicalDocuments.mockResolvedValue([])
    mockedListAnalyses.mockResolvedValue([])
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

  it('shows a breadcrumb ending in the patient’s name and a Back action to the Patients list', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    const user = userEvent.setup()
    renderOverviewPage()

    const breadcrumb = await screen.findByRole('navigation', { name: 'Breadcrumb' })
    expect(within(breadcrumb).getByText('Jane Doe')).toHaveAttribute('aria-current', 'page')

    await user.click(screen.getByRole('button', { name: 'Back to Patients' }))
    expect(mockNavigate).toHaveBeenCalledWith('/patients')
  })

  it('shows the empty medications state with a link to add the first one', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    renderOverviewPage()

    expect(
      await screen.findByRole('heading', { name: 'No medications added yet' }),
    ).toBeInTheDocument()
    const addLink = screen.getByRole('link', { name: 'Add your first medication' })
    expect(addLink).toHaveAttribute('href', '/patients/1/medications')
    expect(mockedListMedications).toHaveBeenCalledWith(1)
  })

  it('does not show a "View All" link when there are no medications to view', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    renderOverviewPage()

    await screen.findByRole('heading', { name: 'No medications added yet' })
    expect(screen.queryByRole('link', { name: 'View all medications' })).not.toBeInTheDocument()
  })

  it('shows a "View All" link to the full Medications page when medications exist', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedListMedications.mockResolvedValue([sampleMedication])
    renderOverviewPage()

    const link = await screen.findByRole('link', { name: 'View all medications' })
    expect(link).toHaveTextContent('View All')
    expect(link).toHaveAttribute('href', '/patients/1/medications')
  })

  it('shows the patient medication list, reusing the shared medication card', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedListMedications.mockResolvedValue([sampleMedication])
    renderOverviewPage()

    expect(await screen.findByRole('heading', { name: 'Lisinopril' })).toBeInTheDocument()
    expect(screen.getByText('10 mg')).toBeInTheDocument()
  })

  it('shows an error state for the medication list independent of the patient details', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedListMedications.mockRejectedValue({ status: 500, message: 'Could not load medications.' })
    renderOverviewPage()

    await screen.findByRole('heading', { name: 'Jane Doe' })
    expect(await screen.findByText('Could not load medications.')).toBeInTheDocument()
  })

  it('edits a medication directly from the overview page', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedListMedications.mockResolvedValue([sampleMedication])
    mockedUpdateMedication.mockResolvedValue({ ...sampleMedication, dose: '20 mg' })
    const user = userEvent.setup()
    renderOverviewPage()

    await screen.findByRole('heading', { name: 'Lisinopril' })
    await user.click(screen.getByRole('button', { name: 'Edit' }))

    const saveButton = screen.getByRole('button', { name: 'Save' })
    const editForm = saveButton.closest('form')!
    const doseInput = within(editForm).getByLabelText('Dosage')
    await user.clear(doseInput)
    await user.type(doseInput, '20 mg')
    await user.click(saveButton)

    await waitFor(() =>
      expect(mockedUpdateMedication).toHaveBeenCalledWith(
        1,
        5,
        expect.objectContaining({ dose: '20 mg' }),
      ),
    )
  })

  it('deletes a medication directly from the overview page', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedListMedications.mockResolvedValue([sampleMedication])
    mockedDeleteMedication.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderOverviewPage()

    await screen.findByRole('heading', { name: 'Lisinopril' })
    await user.click(screen.getByRole('button', { name: 'Delete Lisinopril' }))

    await waitFor(() => expect(mockedDeleteMedication).toHaveBeenCalledWith(1, 5))
  })

  it('links the Quick Actions to Create Analysis, Upload, and Medications for this patient', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    renderOverviewPage()

    expect(await screen.findByRole('link', { name: 'Create Analysis' })).toHaveAttribute(
      'href',
      '/patients/1/analyses/new',
    )
    expect(screen.getByRole('link', { name: 'Upload document' })).toHaveAttribute(
      'href',
      '/patients/1/upload',
    )
    expect(screen.getByRole('link', { name: 'Manage medications' })).toHaveAttribute(
      'href',
      '/patients/1/medications',
    )
  })

  it('shows a "View All" link to the full Clinical Documents page when documents exist', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedListClinicalDocuments.mockResolvedValue([sampleDocument])
    renderOverviewPage()

    const link = await screen.findByRole('link', { name: 'View all clinical documents' })
    expect(link).toHaveTextContent('View All')
    expect(link).toHaveAttribute('href', '/patients/1/documents')
  })

  it('does not show a "View All" link when there are no documents to view', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    renderOverviewPage()

    await screen.findByText('No documents uploaded')
    expect(
      screen.queryByRole('link', { name: 'View all clinical documents' }),
    ).not.toBeInTheDocument()
  })

  it('shows a breadcrumb naming Patients and the current patient', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    renderOverviewPage()

    const breadcrumb = await screen.findByRole('navigation', { name: 'Breadcrumb' })
    expect(within(breadcrumb).getByRole('link', { name: 'Patients' })).toHaveAttribute(
      'href',
      '/patients',
    )
    expect(within(breadcrumb).getByText('Jane Doe')).toHaveAttribute('aria-current', 'page')
  })

  it('shows the empty documents state and a link to upload the first one', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    renderOverviewPage()

    expect(await screen.findByText('No documents uploaded')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Upload your first document' })).toHaveAttribute(
      'href',
      '/patients/1/upload',
    )
    expect(mockedListClinicalDocuments).toHaveBeenCalledWith(1)
  })

  it('shows a compact preview of recent documents with no delete action', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedListClinicalDocuments.mockResolvedValue([sampleDocument])
    renderOverviewPage()

    expect(await screen.findByText('Initial Visit')).toBeInTheDocument()
    expect(screen.getByText(/Visit note/)).toBeInTheDocument()

    // Full document management (delete) lives on the dedicated Clinical
    // Documents page instead; only viewing is available from the preview.
    expect(screen.queryByRole('button', { name: 'Delete Initial Visit' })).not.toBeInTheDocument()
  })

  it('lets a recent document card be clicked to view its extracted text', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedListClinicalDocuments.mockResolvedValue([sampleDocument])
    const user = userEvent.setup()
    renderOverviewPage()

    await screen.findByText('Initial Visit')
    const toggle = screen.getByRole('button', { name: 'View Initial Visit' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Patient presents with hypertension.')).not.toBeInTheDocument()

    await user.click(toggle)

    expect(screen.getByRole('button', { name: 'Hide Initial Visit' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(screen.getByText('Patient presents with hypertension.')).toBeInTheDocument()
  })

  it('shows only the most recent documents in the preview, newest first', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    const documents = Array.from({ length: 7 }, (_, index) =>
      makeDocument({
        id: index + 1,
        title: `Document ${index + 1}`,
        created_at: `2026-01-0${index + 1}T00:00:00Z`,
      }),
    )
    mockedListClinicalDocuments.mockResolvedValue(documents)
    renderOverviewPage()

    await screen.findByText('Document 1')
    const titles = screen.getAllByRole('heading', { level: 4 }).map((el) => el.textContent)
    expect(titles).toEqual(['Document 1', 'Document 2', 'Document 3'])
    expect(screen.queryByText('Document 4')).not.toBeInTheDocument()
  })

  it('shows an error state for the document list independent of the patient details', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedListClinicalDocuments.mockRejectedValue({
      status: 500,
      message: 'Could not load documents.',
    })
    renderOverviewPage()

    await screen.findByRole('heading', { name: 'Jane Doe' })
    expect(await screen.findByText('Could not load documents.')).toBeInTheDocument()
  })

  it('shows the empty analyses state with a link to start one', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    renderOverviewPage()

    expect(await screen.findByText('No analyses yet')).toBeInTheDocument()
    expect(mockedListAnalyses).toHaveBeenCalledWith(1, 3)
  })

  it('does not show a "View All" link when there are no analyses to view', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    renderOverviewPage()

    await screen.findByText('No analyses yet')
    expect(screen.queryByRole('link', { name: 'View all analyses' })).not.toBeInTheDocument()
  })

  it('shows a preview of recent analyses with a link to the full history', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedListAnalyses.mockResolvedValue([sampleAnalysis])
    renderOverviewPage()

    expect(await screen.findByText('Reconciliation completed with 1 finding.')).toBeInTheDocument()
    const link = screen.getByRole('link', { name: 'View all analyses' })
    expect(link).toHaveTextContent('View All')
    expect(link).toHaveAttribute('href', '/patients/1/analyses')
  })

  it('standardizes every preview section on the same "View All" label, distinguished for screen readers by aria-label', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedListClinicalDocuments.mockResolvedValue([sampleDocument])
    mockedListAnalyses.mockResolvedValue([sampleAnalysis])
    mockedListMedications.mockResolvedValue([sampleMedication])
    renderOverviewPage()

    const medicationsLink = await screen.findByRole('link', { name: 'View all medications' })
    const documentsLink = screen.getByRole('link', { name: 'View all clinical documents' })
    const analysesLink = screen.getByRole('link', { name: 'View all analyses' })

    // Same visible label everywhere; the standardization this issue asks for.
    for (const link of [medicationsLink, documentsLink, analysesLink]) {
      expect(link).toHaveTextContent('View All')
    }

    // Distinct accessible names (from aria-label) so a screen reader user
    // encountering three identically-worded links can still tell them apart.
    expect(medicationsLink).toHaveAttribute('href', '/patients/1/medications')
    expect(documentsLink).toHaveAttribute('href', '/patients/1/documents')
    expect(analysesLink).toHaveAttribute('href', '/patients/1/analyses')
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
