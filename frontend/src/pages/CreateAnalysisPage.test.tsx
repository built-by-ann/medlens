import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  createMemoryRouter,
  MemoryRouter,
  Route,
  RouterProvider,
  Routes,
  useLocation,
} from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CreateAnalysisPage } from '@/pages/CreateAnalysisPage'
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
    <MemoryRouter initialEntries={['/patients/7/analyses/new']}>
      <Routes>
        <Route path="/patients/:patientId/analyses/new" element={<CreateAnalysisPage />} />
        <Route path="/patients/:patientId/analyses/processing" element={<ProcessingProbe />} />
        <Route path="/patients/:patientId" element={<div>Patient Overview stub</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

function getFileInput(): HTMLInputElement {
  return screen.getByTestId('file-input')
}

// The separate "N documents selected" line was removed as a redundant
// duplicate of this heading's own count - the heading itself is now the
// live-updating source of truth every selection-count assertion checks.
function selectedDocumentsHeading(count: number): string {
  return `Selected Documents (${count})`
}

describe('CreateAnalysisPage', () => {
  beforeEach(() => {
    mockedGetPatient.mockReset()
    mockedListClinicalDocuments.mockReset()
    mockedGetPatient.mockResolvedValue(patient)
    mockedListClinicalDocuments.mockResolvedValue([documentA, documentB])
  })

  it('shows a loading state while the patient is being fetched', () => {
    mockedGetPatient.mockReturnValue(new Promise(() => {}))
    renderPage()

    expect(screen.getByRole('status')).toHaveTextContent('Loading patient')
  })

  it('shows a breadcrumb and page heading', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Create Analysis' })).toBeInTheDocument()
    const breadcrumb = screen.getByRole('navigation', { name: 'Breadcrumb' })
    expect(within(breadcrumb).getByRole('link', { name: 'Jane Doe' })).toHaveAttribute(
      'href',
      '/patients/7',
    )
    expect(within(breadcrumb).getByText('Create Analysis')).toHaveAttribute('aria-current', 'page')
  })

  it('has a Back action to the patient overview', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })
    await user.click(screen.getByRole('button', { name: 'Back to Jane Doe' }))

    expect(await screen.findByText('Patient Overview stub')).toBeInTheDocument()
  })

  it('has a Cancel link next to Create Analysis that leaves without submitting anything', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })
    await user.click(screen.getByRole('checkbox', { name: /March Visit Note/ }))

    await user.click(screen.getByRole('link', { name: 'Cancel' }))

    expect(await screen.findByText('Patient Overview stub')).toBeInTheDocument()
  })

  it('replaces its own history entry on Cancel, so the browser back button never returns to it', async () => {
    // Reproduces a reported bug: Cancel used to push a new history entry
    // instead of replacing the current one, so pressing the browser back
    // button (or an in-app "Back to X" control relying on real history,
    // like BackButton) from the page Cancel lands on would go back to this
    // cancelled Create Analysis page instead of skipping over it.
    const user = userEvent.setup()
    const router = createMemoryRouter(
      [
        { path: '/patients/:patientId/analyses/new', element: <CreateAnalysisPage /> },
        { path: '/patients/:patientId', element: <div>Patient Overview stub</div> },
      ],
      { initialEntries: ['/patients/7', '/patients/7/analyses/new'], initialIndex: 1 },
    )
    render(<RouterProvider router={router} />)

    await screen.findByRole('heading', { name: 'Create Analysis' })
    await user.click(screen.getByRole('link', { name: 'Cancel' }))
    expect(await screen.findByText('Patient Overview stub')).toBeInTheDocument()

    router.navigate(-1)

    await waitFor(() => expect(router.state.location.pathname).not.toBe('/patients/7/analyses/new'))
  })

  it('lists every existing document with its title, type, and upload date, each behind a checkbox', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })
    const existingSection = screen.getByRole('region', { name: 'Existing Documents' })

    const checkboxA = screen.getByRole('checkbox', { name: /March Visit Note/ })
    expect(checkboxA).not.toBeChecked()
    expect(within(existingSection).getByText(/Visit note/)).toBeInTheDocument()

    const checkboxB = screen.getByRole('checkbox', { name: /Discharge Summary/ })
    expect(checkboxB).not.toBeChecked()
    expect(within(existingSection).getByText(/Discharge summary/)).toBeInTheDocument()
  })

  it('disables Create Analysis until at least one document is selected', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    const submitButton = screen.getByRole('button', { name: 'Create Analysis' })
    expect(submitButton).toBeDisabled()
    expect(screen.getByText(selectedDocumentsHeading(0))).toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: /March Visit Note/ }))

    expect(submitButton).toBeEnabled()
    expect(screen.getByText(selectedDocumentsHeading(1))).toBeInTheDocument()
  })

  it('supports selecting and deselecting multiple existing documents, updating the count', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    const checkboxA = screen.getByRole('checkbox', { name: /March Visit Note/ })
    const checkboxB = screen.getByRole('checkbox', { name: /Discharge Summary/ })

    await user.click(checkboxA)
    await user.click(checkboxB)
    expect(screen.getByText(selectedDocumentsHeading(2))).toBeInTheDocument()
    expect(checkboxA).toBeChecked()
    expect(checkboxB).toBeChecked()

    await user.click(checkboxA)
    expect(screen.getByText(selectedDocumentsHeading(1))).toBeInTheDocument()
    expect(checkboxA).not.toBeChecked()
    expect(checkboxB).toBeChecked()
  })

  it('is keyboard operable: tabbing to a checkbox and pressing space toggles it', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    const checkboxA = screen.getByRole('checkbox', { name: /March Visit Note/ })
    checkboxA.focus()
    expect(checkboxA).toHaveFocus()

    await user.keyboard('[Space]')
    expect(checkboxA).toBeChecked()
  })

  it('shows a selected existing document in the Selected Documents summary, removable from there too', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })
    await user.click(screen.getByRole('checkbox', { name: /March Visit Note/ }))

    const summary = screen.getByRole('region', { name: /Selected Documents/ })
    expect(within(summary).getByText('March Visit Note')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Remove March Visit Note from selection' }))

    expect(screen.getByRole('checkbox', { name: /March Visit Note/ })).not.toBeChecked()
    expect(screen.getByText(selectedDocumentsHeading(0))).toBeInTheDocument()
  })

  it('uploading a new file immediately adds it to the selection without restarting the workflow', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)

    expect(screen.getByText(selectedDocumentsHeading(1))).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create Analysis' })).toBeEnabled()
    expect(screen.getByText(/note\.txt/)).toBeInTheDocument()
  })

  it('confirms an uploaded file right in Upload Additional Documents, not just in the summary count', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)

    const uploadSection = screen.getByRole('region', { name: 'Upload Additional Documents' })
    expect(within(uploadSection).getByText(/note\.txt/)).toBeInTheDocument()
    expect(
      within(uploadSection).getByRole('button', { name: 'Remove note.txt' }),
    ).toBeInTheDocument()

    const summary = screen.getByRole('region', { name: /Selected Documents/ })
    expect(
      within(summary).getByText('Uploaded files are listed above, in Upload Additional Documents.'),
    ).toBeInTheDocument()
  })

  it('warns when an uploaded file shares its title with a document already on file', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    const file = new File(['hello'], 'March Visit Note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)

    expect(
      screen.getByText('A document named "March Visit Note" already exists for this patient.'),
    ).toBeInTheDocument()
  })

  it('does not warn when an uploaded file has no matching existing document', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)

    expect(screen.queryByText(/already exists for this patient/)).not.toBeInTheDocument()
  })

  it('renaming an uploaded file updates whether it warns about an existing document', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)

    expect(screen.queryByText(/already exists for this patient/)).not.toBeInTheDocument()

    const fileTitleInput = screen.getAllByLabelText('Title (optional)')[0]!
    await user.type(fileTitleInput, 'March Visit Note')

    expect(
      screen.getByText('A document named "March Visit Note" already exists for this patient.'),
    ).toBeInTheDocument()

    await user.clear(fileTitleInput)

    expect(screen.queryByText(/already exists for this patient/)).not.toBeInTheDocument()
  })

  it('submits an uploaded file with its edited title instead of the filename-derived one', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)
    await user.type(screen.getAllByLabelText('Title (optional)')[0]!, 'Renamed Note')

    await user.click(screen.getByRole('button', { name: 'Create Analysis' }))

    const probe = await screen.findByTestId('processing-probe')
    const state = JSON.parse(probe.textContent ?? 'null')
    expect(state.files).toEqual([
      { id: 0, file: {}, documentType: 'visit_note', title: 'Renamed Note' },
    ])
  })

  it('adding a pasted note immediately adds it to the selection', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    await user.type(screen.getByLabelText('Note text'), 'Pasted note text')
    await user.click(screen.getByRole('button', { name: 'Add note' }))

    expect(screen.getByText(selectedDocumentsHeading(1))).toBeInTheDocument()
    expect(screen.getByText('Note 1')).toBeInTheDocument()
  })

  it('renumbers untitled notes by their position after one is removed, instead of skipping numbers', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    async function addNote(text: string) {
      await user.type(screen.getByLabelText('Note text'), text)
      await user.click(screen.getByRole('button', { name: 'Add note' }))
    }

    await addNote('First note')
    await addNote('Second note')
    await addNote('Third note')

    expect(screen.getByText('Note 1')).toBeInTheDocument()
    expect(screen.getByText('Note 2')).toBeInTheDocument()
    expect(screen.getByText('Note 3')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Remove Note 2' }))
    expect(screen.queryByText('Second note')).not.toBeInTheDocument()

    await addNote('Fourth note')

    // The newly added note fills the now-vacant second slot by position -
    // it's still just "Note 1", "Note 2", "Note 3", never "Note 4".
    expect(screen.getByText('Note 1')).toBeInTheDocument()
    expect(screen.getByText('Note 2')).toBeInTheDocument()
    expect(screen.getByText('Note 3')).toBeInTheDocument()
    expect(screen.queryByText('Note 4')).not.toBeInTheDocument()
  })

  it('rejects an unsupported file type without adding it to the selection', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    const file = new File(['bad'], 'note.exe', { type: 'application/octet-stream' })
    const dropzone = screen.getByRole('button', { name: /Upload clinical note files/ })
    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } })

    expect(await screen.findByRole('alert')).toHaveTextContent('not a supported file type')
    expect(screen.getByText(selectedDocumentsHeading(0))).toBeInTheDocument()
  })

  it('removes a queued file from the selection', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)
    expect(screen.getByText(selectedDocumentsHeading(1))).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Remove note.txt' }))

    expect(screen.getByText(selectedDocumentsHeading(0))).toBeInTheDocument()
  })

  it('combines existing and newly uploaded documents into a single analysis submission', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    await user.click(screen.getByRole('checkbox', { name: /March Visit Note/ }))
    await user.click(screen.getByRole('checkbox', { name: /Discharge Summary/ }))

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)

    await user.type(screen.getByLabelText('Note text'), 'Pasted note text')
    await user.click(screen.getByRole('button', { name: 'Add note' }))

    expect(screen.getByText(selectedDocumentsHeading(4))).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Create Analysis' }))

    const probe = await screen.findByTestId('processing-probe')
    expect(JSON.parse(probe.textContent ?? 'null')).toEqual({
      files: [{ id: 0, file: {}, documentType: 'visit_note' }],
      notes: [{ id: 0, title: '', rawText: 'Pasted note text', documentType: 'visit_note' }],
      existingDocumentIds: [1, 2],
    })
  })

  it('accepts a CSV medication list, combining it with an existing document and a plain text upload in one submission', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    await user.click(screen.getByRole('checkbox', { name: /March Visit Note/ }))

    const textFile = new File(['Patient reports improvement.'], 'note.txt', {
      type: 'text/plain',
    })
    const csvFile = new File(['medication_name,dose\nLisinopril,10mg'], 'medications.csv', {
      type: 'text/csv',
    })
    await user.upload(getFileInput(), [textFile, csvFile])

    // Confirmed right in Upload Additional Documents, the same as any other
    // file - there's no separate "CSV upload" mode or UI.
    const uploadSection = screen.getByRole('region', { name: 'Upload Additional Documents' })
    expect(within(uploadSection).getByText(/medications\.csv/)).toBeInTheDocument()

    expect(screen.getByText(selectedDocumentsHeading(3))).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Create Analysis' }))

    const probe = await screen.findByTestId('processing-probe')
    expect(JSON.parse(probe.textContent ?? 'null')).toEqual({
      files: [
        { id: 0, file: {}, documentType: 'visit_note' },
        { id: 1, file: {}, documentType: 'medication_list' },
      ],
      notes: [],
      existingDocumentIds: [1],
    })
  })

  it('advertises CSV as a supported upload format on the (keyboard-accessible) dropzone', async () => {
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    const dropzone = screen.getByRole('button', { name: /Upload clinical note files/ })
    expect(dropzone).toHaveAccessibleName(/\.csv/)
    expect(dropzone).toHaveAttribute('tabIndex', '0')
  })

  it('navigates with only existing document ids when nothing was uploaded', async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Create Analysis' })

    await user.click(screen.getByRole('checkbox', { name: /March Visit Note/ }))
    await user.click(screen.getByRole('button', { name: 'Create Analysis' }))

    const probe = await screen.findByTestId('processing-probe')
    expect(JSON.parse(probe.textContent ?? 'null')).toEqual({
      files: [],
      notes: [],
      existingDocumentIds: [1],
    })
  })

  it('shows an empty state for existing documents but still allows uploading a new one', async () => {
    mockedListClinicalDocuments.mockResolvedValue([])
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText('No documents uploaded')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Upload your first document/ })).toHaveAttribute(
      'href',
      '/patients/7/upload',
    )
    expect(screen.getByRole('button', { name: 'Create Analysis' })).toBeDisabled()

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)

    expect(screen.getByRole('button', { name: 'Create Analysis' })).toBeEnabled()
  })

  it('shows a not-found error when the patient does not exist or is not owned by the user', async () => {
    mockedGetPatient.mockRejectedValue({ status: 404, message: 'Patient not found' })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Patient not found')
  })

  it('scopes an existing-documents load failure to that section, while upload still works', async () => {
    mockedListClinicalDocuments.mockRejectedValue({ status: 500, message: 'Server error.' })
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Server error.')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()

    // The rest of the page - uploading a new document - still works even
    // though the existing-documents section failed to load.
    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)

    expect(screen.getByText(selectedDocumentsHeading(1))).toBeInTheDocument()
  })

  describe('searching and paging existing documents', () => {
    it('narrows the existing-documents list by title or document type', async () => {
      const user = userEvent.setup()
      renderPage()

      await screen.findByRole('heading', { name: 'Create Analysis' })
      const search = screen.getByLabelText('Search existing documents')

      await user.type(search, 'discharge')

      expect(screen.queryByRole('checkbox', { name: /March Visit Note/ })).not.toBeInTheDocument()
      expect(screen.getByRole('checkbox', { name: /Discharge Summary/ })).toBeInTheDocument()
    })

    it('shows a message when the search matches no existing documents', async () => {
      const user = userEvent.setup()
      renderPage()

      await screen.findByRole('heading', { name: 'Create Analysis' })
      await user.type(screen.getByLabelText('Search existing documents'), 'nonexistent document')

      expect(screen.getByText('No documents match your search.')).toBeInTheDocument()
      expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    })

    it('caps the existing-documents list with a Show more action once there are many', async () => {
      const manyDocuments = Array.from({ length: 10 }, (_, index) =>
        makeDocument({ id: index + 1, title: `Document ${index + 1}` }),
      )
      mockedListClinicalDocuments.mockResolvedValue(manyDocuments)
      const user = userEvent.setup()
      renderPage()

      await screen.findByRole('heading', { name: 'Create Analysis' })

      expect(screen.getByRole('checkbox', { name: /Document 1\b/ })).toBeInTheDocument()
      expect(screen.getByRole('checkbox', { name: /Document 3\b/ })).toBeInTheDocument()
      expect(screen.queryByRole('checkbox', { name: /Document 4\b/ })).not.toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'Show 7 more' }))

      expect(screen.getByRole('checkbox', { name: /Document 4\b/ })).toBeInTheDocument()
      expect(screen.getByRole('checkbox', { name: /Document 10\b/ })).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'Show less' }))

      expect(screen.queryByRole('checkbox', { name: /Document 4\b/ })).not.toBeInTheDocument()
    })

    it('resets to the collapsed view when the search query changes', async () => {
      const manyDocuments = Array.from({ length: 10 }, (_, index) =>
        makeDocument({ id: index + 1, title: `Document ${index + 1}` }),
      )
      mockedListClinicalDocuments.mockResolvedValue(manyDocuments)
      const user = userEvent.setup()
      renderPage()

      await screen.findByRole('heading', { name: 'Create Analysis' })
      await user.click(screen.getByRole('button', { name: 'Show 7 more' }))
      expect(screen.getByRole('checkbox', { name: /Document 4\b/ })).toBeInTheDocument()

      await user.type(screen.getByLabelText('Search existing documents'), 'D')

      expect(screen.queryByRole('checkbox', { name: /Document 4\b/ })).not.toBeInTheDocument()
    })
  })
})
