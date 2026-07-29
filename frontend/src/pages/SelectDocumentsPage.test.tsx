import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SelectDocumentsPage } from '@/pages/SelectDocumentsPage'
import { getPatient } from '@/api/patients'
import { listClinicalDocuments } from '@/api/clinicalDocuments'
import type { ClinicalDocument, Patient } from '@/types/api'

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    getPatient: vi.fn(),
  }
})

vi.mock('@/api/clinicalDocuments', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/clinicalDocuments')>()

  return {
    ...actual,
    listClinicalDocuments: vi.fn(),
  }
})

const mockedGetPatient = vi.mocked(getPatient)
const mockedListClinicalDocuments = vi.mocked(listClinicalDocuments)

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

function makeDocument(overrides: Partial<ClinicalDocument> = {}): ClinicalDocument {
  return {
    id: 1,
    patient_id: 7,
    document_type: 'visit_note',
    title: 'March Visit Note',
    raw_text: 'Patient takes Lisinopril 10 mg.',
    file_name: null,
    file_type: 'manual_entry',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    analysis_count: 0,
    ...overrides,
  }
}

const documentA = makeDocument({ id: 1, title: 'March Visit Note', document_type: 'visit_note' })
const documentB = makeDocument({
  id: 2,
  title: 'Discharge Summary',
  document_type: 'discharge_summary',
  created_at: '2026-02-01T00:00:00Z',
})

// Stands in for AnalysisProcessingPage: submission happens there, so this
// page's job is just to navigate with the right router state.
function ProcessingProbe() {
  const location = useLocation()
  return <div data-testid="processing-probe">{JSON.stringify(location.state)}</div>
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/patients/7/analyses/select-documents']}>
      <Routes>
        <Route
          path="/patients/:patientId/analyses/select-documents"
          element={<SelectDocumentsPage />}
        />
        <Route path="/patients/:patientId/analyses/processing" element={<ProcessingProbe />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('SelectDocumentsPage', () => {
  beforeEach(() => {
    mockedGetPatient.mockReset()
    mockedListClinicalDocuments.mockReset()
    mockedGetPatient.mockResolvedValue(patient)
    mockedListClinicalDocuments.mockResolvedValue([documentA, documentB])
  })

  it('shows a loading state while the patient and documents are being fetched', () => {
    mockedListClinicalDocuments.mockReturnValue(new Promise(() => {}))
    renderPage()

    expect(screen.getByRole('status')).toHaveTextContent('Loading documents')
  })

  it('shows a breadcrumb and page heading', async () => {
    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'Select existing documents' }),
    ).toBeInTheDocument()
    const breadcrumb = screen.getByRole('navigation', { name: 'Breadcrumb' })
    expect(within(breadcrumb).getByRole('link', { name: 'Jane Doe' })).toHaveAttribute(
      'href',
      '/patients/7',
    )
    expect(within(breadcrumb).getByText('Select documents')).toHaveAttribute('aria-current', 'page')
  })

  it('lists every document with its title, type, and upload date, each behind a checkbox', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'Select existing documents' })

    const checkboxA = screen.getByRole('checkbox', { name: /March Visit Note/ })
    expect(checkboxA).not.toBeChecked()
    expect(screen.getByText(/Visit note/)).toBeInTheDocument()

    const checkboxB = screen.getByRole('checkbox', { name: /Discharge Summary/ })
    expect(checkboxB).not.toBeChecked()
    expect(screen.getByText(/Discharge summary/)).toBeInTheDocument()
  })

  it('disables Create Analysis until at least one document is selected', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Select existing documents' })

    const submitButton = screen.getByRole('button', { name: 'Create Analysis' })
    expect(submitButton).toBeDisabled()
    expect(screen.getByText('0 of 2 documents selected')).toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: /March Visit Note/ }))

    expect(submitButton).toBeEnabled()
    expect(screen.getByText('1 of 2 documents selected')).toBeInTheDocument()
  })

  it('supports selecting and deselecting multiple documents, updating the count', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Select existing documents' })

    const checkboxA = screen.getByRole('checkbox', { name: /March Visit Note/ })
    const checkboxB = screen.getByRole('checkbox', { name: /Discharge Summary/ })

    await user.click(checkboxA)
    await user.click(checkboxB)
    expect(screen.getByText('2 of 2 documents selected')).toBeInTheDocument()
    expect(checkboxA).toBeChecked()
    expect(checkboxB).toBeChecked()

    await user.click(checkboxA)
    expect(screen.getByText('1 of 2 documents selected')).toBeInTheDocument()
    expect(checkboxA).not.toBeChecked()
    expect(checkboxB).toBeChecked()
  })

  it('is keyboard operable: tabbing to a checkbox and pressing space toggles it', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Select existing documents' })

    const checkboxA = screen.getByRole('checkbox', { name: /March Visit Note/ })
    checkboxA.focus()
    expect(checkboxA).toHaveFocus()

    await user.keyboard('[Space]')
    expect(checkboxA).toBeChecked()
  })

  it('navigates to the Analysis Processing page with the selected document ids on submit', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Select existing documents' })

    await user.click(screen.getByRole('checkbox', { name: /March Visit Note/ }))
    await user.click(screen.getByRole('checkbox', { name: /Discharge Summary/ }))
    await user.click(screen.getByRole('button', { name: 'Create Analysis' }))

    const probe = await screen.findByTestId('processing-probe')
    expect(JSON.parse(probe.textContent ?? 'null')).toEqual({
      files: [],
      notes: [],
      existingDocumentIds: [1, 2],
    })
  })

  it('shows an empty state with a link to upload when the patient has no documents', async () => {
    mockedListClinicalDocuments.mockResolvedValue([])
    renderPage()

    expect(await screen.findByText('No documents uploaded')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Upload your first document/ })).toHaveAttribute(
      'href',
      '/patients/7/upload',
    )
    expect(screen.queryByRole('button', { name: 'Create Analysis' })).not.toBeInTheDocument()
  })

  it('shows a not-found error when the patient does not exist or is not owned by the user', async () => {
    mockedGetPatient.mockRejectedValue({ status: 404, message: 'Patient not found' })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Patient not found')
  })

  it('shows an error state when documents fail to load, with a retry option', async () => {
    mockedListClinicalDocuments.mockRejectedValue({ status: 500, message: 'Server error.' })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Server error.')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
