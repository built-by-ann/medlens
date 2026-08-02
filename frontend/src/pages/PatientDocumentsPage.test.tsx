import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PatientDocumentsPage } from '@/pages/PatientDocumentsPage'
import { getPatient } from '@/api/patients'
import { deleteClinicalDocument, listClinicalDocuments } from '@/api/clinicalDocuments'
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
    deleteClinicalDocument: vi.fn(),
  }
})

const mockedGetPatient = vi.mocked(getPatient)
const mockedListClinicalDocuments = vi.mocked(listClinicalDocuments)
const mockedDeleteClinicalDocument = vi.mocked(deleteClinicalDocument)

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

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/patients/7/documents']}>
      <Routes>
        <Route path="/patients/:patientId/documents" element={<PatientDocumentsPage />} />
        <Route path="/patients/:patientId" element={<div>Patient Overview stub</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('PatientDocumentsPage', () => {
  beforeEach(() => {
    mockedGetPatient.mockReset()
    mockedListClinicalDocuments.mockReset()
    mockedDeleteClinicalDocument.mockReset()
    mockedGetPatient.mockResolvedValue(patient)
    mockedListClinicalDocuments.mockResolvedValue([])
  })

  it('shows a loading state while the patient is being fetched', () => {
    mockedGetPatient.mockReturnValue(new Promise(() => {}))
    renderPage()

    expect(screen.getByRole('status')).toHaveTextContent('Loading patient')
  })

  it('shows the page heading, description, and breadcrumb', async () => {
    mockedListClinicalDocuments.mockResolvedValue([])
    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'Clinical Documents', level: 1 }),
    ).toBeInTheDocument()
    expect(screen.getByText('Complete document history for Jane Doe')).toBeInTheDocument()

    const breadcrumb = screen.getByRole('navigation', { name: 'Breadcrumb' })
    expect(within(breadcrumb).getByRole('link', { name: 'Jane Doe' })).toHaveAttribute(
      'href',
      '/patients/7',
    )
    expect(within(breadcrumb).getByText('Clinical Documents')).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('has a Back action to the patient overview', async () => {
    mockedListClinicalDocuments.mockResolvedValue([])
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Clinical Documents', level: 1 })
    await user.click(screen.getByRole('button', { name: 'Back to Jane Doe' }))

    expect(await screen.findByText('Patient Overview stub')).toBeInTheDocument()
  })

  it('provides Upload Documents, Create Analysis, and View Patient actions', async () => {
    mockedListClinicalDocuments.mockResolvedValue([])
    renderPage()

    await screen.findByRole('heading', { name: 'Clinical Documents', level: 1 })
    const nav = screen.getByRole('navigation', { name: 'Document actions' })

    expect(within(nav).getByRole('link', { name: 'Upload Documents' })).toHaveAttribute(
      'href',
      '/patients/7/upload',
    )
    expect(within(nav).getByRole('link', { name: 'Create Analysis' })).toHaveAttribute(
      'href',
      '/patients/7/analyses/new',
    )
    expect(within(nav).getByRole('link', { name: 'View Patient' })).toHaveAttribute(
      'href',
      '/patients/7',
    )
  })

  it('lists every document in the order returned by the backend (most recent first)', async () => {
    mockedListClinicalDocuments.mockResolvedValue([
      makeDocument({ id: 1, title: 'Newest', created_at: '2026-03-01T00:00:00Z' }),
      makeDocument({ id: 2, title: 'Middle', created_at: '2026-02-01T00:00:00Z' }),
      makeDocument({ id: 3, title: 'Oldest', created_at: '2026-01-01T00:00:00Z' }),
    ])
    renderPage()

    await screen.findByText('Newest')
    const titles = screen.getAllByRole('heading', { level: 4 }).map((el) => el.textContent)
    expect(titles).toEqual(['Newest', 'Middle', 'Oldest'])
  })

  it('shows document type, upload date, and analysis count for each document', async () => {
    mockedListClinicalDocuments.mockResolvedValue([
      makeDocument({
        title: 'Discharge Note',
        document_type: 'discharge_summary',
        analysis_count: 2,
      }),
    ])
    renderPage()

    await screen.findByText('Discharge Note')
    expect(screen.getByText(/Discharge summary/)).toBeInTheDocument()
    expect(screen.getByText(/Used in 2 analyses/)).toBeInTheDocument()
  })

  it('shows "Not yet analyzed" for a document with no analyses', async () => {
    mockedListClinicalDocuments.mockResolvedValue([makeDocument({ analysis_count: 0 })])
    renderPage()

    expect(await screen.findByText(/Not yet analyzed/)).toBeInTheDocument()
  })

  it('expands a document by clicking anywhere on its title and metadata', async () => {
    mockedListClinicalDocuments.mockResolvedValue([makeDocument()])
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('March Visit Note')
    expect(screen.queryByText('Patient takes Lisinopril 10 mg.')).not.toBeInTheDocument()

    const toggle = screen.getByRole('button', { name: 'View March Visit Note' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(toggle)

    expect(screen.getByText('Patient takes Lisinopril 10 mg.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Hide March Visit Note' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
  })

  it('deletes a document', async () => {
    mockedListClinicalDocuments.mockResolvedValue([makeDocument()])
    mockedDeleteClinicalDocument.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('March Visit Note')
    await user.click(screen.getByRole('button', { name: 'Delete March Visit Note' }))

    await waitFor(() => expect(mockedDeleteClinicalDocument).toHaveBeenCalledWith(7, 1))
    expect(screen.queryByText('March Visit Note')).not.toBeInTheDocument()
  })

  it('filters the document list by search term', async () => {
    mockedListClinicalDocuments.mockResolvedValue([
      makeDocument({ id: 1, title: 'March Visit Note', document_type: 'visit_note' }),
      makeDocument({ id: 2, title: 'Discharge Summary', document_type: 'discharge_summary' }),
    ])
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('March Visit Note')
    expect(screen.getByText('Discharge Summary')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Search documents'), 'discharge')

    expect(screen.queryByText('March Visit Note')).not.toBeInTheDocument()
    expect(screen.getByText('Discharge Summary')).toBeInTheDocument()
  })

  it('shows a no-match message when the search term matches no document', async () => {
    mockedListClinicalDocuments.mockResolvedValue([makeDocument()])
    const user = userEvent.setup()
    renderPage()

    await screen.findByText('March Visit Note')
    await user.type(screen.getByLabelText('Search documents'), 'nonexistent')

    expect(screen.queryByText('March Visit Note')).not.toBeInTheDocument()
    expect(screen.getByText('No documents match your search.')).toBeInTheDocument()
  })

  it('does not show the search box when there are no documents', async () => {
    mockedListClinicalDocuments.mockResolvedValue([])
    renderPage()

    await screen.findByText('No documents uploaded')
    expect(screen.queryByLabelText('Search documents')).not.toBeInTheDocument()
  })

  it('shows a helpful empty state with an upload action when there are no documents', async () => {
    mockedListClinicalDocuments.mockResolvedValue([])
    renderPage()

    expect(await screen.findByText('No documents uploaded')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Upload your first document/ })).toHaveAttribute(
      'href',
      '/patients/7/upload',
    )
  })

  it('shows an error state when documents fail to load, with a retry option', async () => {
    mockedListClinicalDocuments.mockRejectedValue({ status: 500, message: 'Server error.' })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Server error.')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('shows a not-found error when the patient does not exist or is not owned by the user', async () => {
    mockedGetPatient.mockRejectedValue({ status: 404, message: 'Patient not found' })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Patient not found')
  })
})
