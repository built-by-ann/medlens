import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { UploadPage } from '@/pages/UploadPage'
import { getPatient } from '@/api/patients'
import { createClinicalDocumentFromText, uploadClinicalDocumentFile } from '@/api/clinicalDocuments'
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
    uploadClinicalDocumentFile: vi.fn(),
    createClinicalDocumentFromText: vi.fn(),
  }
})

const mockedGetPatient = vi.mocked(getPatient)
const mockedUploadFile = vi.mocked(uploadClinicalDocumentFile)
const mockedCreateFromText = vi.mocked(createClinicalDocumentFromText)

function fakeDocument(id: number): ClinicalDocument {
  return {
    id,
    patient_id: 7,
    document_type: 'visit_note',
    title: `Document ${id}`,
    raw_text: 'text',
    file_name: null,
    file_type: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    analysis_count: 0,
  }
}

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

function renderUploadPage() {
  return render(
    <MemoryRouter initialEntries={['/patients/7/upload']}>
      <Routes>
        <Route path="/patients/:patientId/upload" element={<UploadPage />} />
        <Route path="/patients/:patientId/documents" element={<div>Documents page stub</div>} />
        <Route path="/patients/:patientId" element={<div>Patient Overview stub</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

// ManualNoteEditor's "add a new note" form is always visible alongside the
// file list and any existing NoteCards, and shares identical labels
// ("Document type", "Note text") with both. These target a specific
// control by its underlying id rather than an ambiguous label match.
function getById<T extends HTMLElement>(container: HTMLElement, id: string): T {
  const element = container.querySelector<T>(`#${id}`)
  if (!element) {
    throw new Error(`No element found with id "${id}"`)
  }
  return element
}

function getFileInput(): HTMLInputElement {
  return screen.getByTestId('file-input')
}

describe('UploadPage', () => {
  beforeEach(() => {
    mockedGetPatient.mockReset()
    mockedUploadFile.mockReset()
    mockedCreateFromText.mockReset()
    mockedGetPatient.mockResolvedValue(patient)
  })

  it('shows a loading state while the patient is being fetched', () => {
    mockedGetPatient.mockReturnValue(new Promise(() => {}))
    renderUploadPage()

    expect(screen.getByRole('status')).toHaveTextContent('Loading patient')
  })

  it('shows the patient name in the page heading', async () => {
    renderUploadPage()

    expect(
      await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ }),
    ).toBeInTheDocument()
  })

  it('shows a breadcrumb trail ending in Upload', async () => {
    const { container } = renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    const breadcrumb = within(container).getByRole('navigation', { name: 'Breadcrumb' })
    expect(within(breadcrumb).getByRole('link', { name: 'Jane Doe' })).toHaveAttribute(
      'href',
      '/patients/7',
    )
    expect(within(breadcrumb).getByText('Upload')).toHaveAttribute('aria-current', 'page')
  })

  it('has a Back action to the patient overview', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })
    await user.click(screen.getByRole('button', { name: 'Back to Jane Doe' }))

    expect(await screen.findByText('Patient Overview stub')).toBeInTheDocument()
  })

  it('adds a selected file to the list, showing its name, size, and a document type defaulting to Visit note', async () => {
    const user = userEvent.setup()
    const { container } = renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    const file = new File(['hello world'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)

    expect(screen.getByText(/note\.txt/)).toBeInTheDocument()
    expect(getById(container, 'file-doctype-0')).toHaveValue('visit_note')
  })

  it('rejects an unsupported file type with a visible, announced error, and does not add it', async () => {
    // Dropped via drag-and-drop, not the input's click-to-browse path: the
    // input's `accept` attribute would filter this out of a real OS file
    // dialog before userEvent.upload() could even "select" it, but a drop
    // is not accept-filtered, so this is the realistic way an unsupported
    // file actually reaches the app.
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    const file = new File(['bad'], 'note.exe', { type: 'application/octet-stream' })
    const dropzone = screen.getByRole('button', { name: /Upload clinical note files/ })

    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } })

    expect(await screen.findByRole('alert')).toHaveTextContent('not a supported file type')
    // The error text itself names the file, so check the file list
    // specifically (its "Remove" button) rather than any mention of the
    // filename anywhere on the page.
    expect(screen.queryByRole('button', { name: 'Remove note.exe' })).not.toBeInTheDocument()
  })

  it('does not add the same file twice', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)
    await user.upload(getFileInput(), file)

    expect(screen.getAllByText(/note\.txt/)).toHaveLength(1)
  })

  it('removes a selected file from the list', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)
    expect(screen.getByText(/note\.txt/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Remove note.txt' }))

    expect(screen.queryByText(/note\.txt/)).not.toBeInTheDocument()
  })

  it('lets a selected file’s document type be changed', async () => {
    const user = userEvent.setup()
    const { container } = renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)

    await user.selectOptions(getById(container, 'file-doctype-0'), 'medication_list')

    expect(getById(container, 'file-doctype-0')).toHaveValue('medication_list')
  })

  it('adds a manually entered note with a document type defaulting to Visit note', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    // Deliberately not named "Visit note" - that string is also the default
    // document type's display label, and this test wants to check the two
    // independently.
    await user.type(screen.getByLabelText('Title (optional)'), 'March visit')
    await user.type(screen.getByLabelText('Note text'), 'Patient takes Lisinopril 10 mg.')
    await user.click(screen.getByRole('button', { name: 'Add note' }))

    expect(screen.getByText('March visit')).toBeInTheDocument()
    expect(screen.getByText('Patient takes Lisinopril 10 mg.')).toBeInTheDocument()
    expect(screen.getByText('Visit note', { selector: 'p' })).toBeInTheDocument()
    // The editor clears after adding, ready for another note.
    expect(screen.getByLabelText('Note text')).toHaveValue('')
  })

  it('shows an accessible validation error when adding a note with no text, and clears it once text is entered', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    await user.click(screen.getByRole('button', { name: 'Add note' }))

    const noteText = screen.getByLabelText('Note text')
    expect(await screen.findByRole('alert')).toHaveTextContent('Note text is required.')
    expect(noteText).toHaveAttribute('aria-invalid', 'true')
    expect(noteText).toHaveAccessibleDescription('Note text is required.')

    await user.type(noteText, 'Patient reports improvement.')

    expect(screen.queryByText('Note text is required.')).not.toBeInTheDocument()
    expect(noteText).not.toHaveAttribute('aria-invalid')
  })

  it('removes a manually entered note', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    await user.type(screen.getByLabelText('Note text'), 'Some note text')
    await user.click(screen.getByRole('button', { name: 'Add note' }))
    expect(screen.getByText('Some note text')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Remove Note 1/ }))

    expect(screen.queryByText('Some note text')).not.toBeInTheDocument()
  })

  it('lets a note’s text be edited', async () => {
    const user = userEvent.setup()
    const { container } = renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    await user.type(screen.getByLabelText('Note text'), 'Original text')
    await user.click(screen.getByRole('button', { name: 'Add note' }))

    await user.click(screen.getByRole('button', { name: 'Edit' }))
    const editTextbox = getById<HTMLTextAreaElement>(container, 'note-text-0')
    await user.clear(editTextbox)
    await user.type(editTextbox, 'Edited text')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(screen.getByText('Edited text')).toBeInTheDocument()
  })

  it('shows an accessible validation error when saving an edited note with no text', async () => {
    const user = userEvent.setup()
    const { container } = renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    await user.type(screen.getByLabelText('Note text'), 'Original text')
    await user.click(screen.getByRole('button', { name: 'Add note' }))

    await user.click(screen.getByRole('button', { name: 'Edit' }))
    const editTextbox = getById<HTMLTextAreaElement>(container, 'note-text-0')
    await user.clear(editTextbox)
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Note text is required.')
    expect(editTextbox).toHaveAttribute('aria-invalid', 'true')
    // The note was never saved with empty text - still editing, original
    // text never got cleared.
    expect(editTextbox).toHaveValue('')
  })

  it('blocks saving when nothing has been added', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    await user.click(screen.getByRole('button', { name: 'Save documents' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Add at least one file or note before saving.',
    )
    expect(mockedUploadFile).not.toHaveBeenCalled()
  })

  it('saves documents without starting an analysis, then goes to the Clinical Documents page', async () => {
    mockedUploadFile.mockResolvedValue(fakeDocument(1))
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)

    await user.click(screen.getByRole('button', { name: 'Save documents' }))

    await waitFor(() =>
      expect(mockedUploadFile).toHaveBeenCalledWith(7, file, 'visit_note', undefined),
    )
    expect(await screen.findByText('Documents page stub')).toBeInTheDocument()
  })

  it('shows a saving state and disables the action while saving is in flight', async () => {
    let resolveUpload: (document: ClinicalDocument) => void = () => {}
    mockedUploadFile.mockReturnValue(
      new Promise((resolve) => {
        resolveUpload = resolve
      }),
    )
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)
    await user.click(screen.getByRole('button', { name: 'Save documents' }))

    const savingButton = await screen.findByRole('button', { name: 'Saving...' })
    expect(savingButton).toBeDisabled()

    resolveUpload(fakeDocument(1))
    await screen.findByText('Documents page stub')
  })

  it('shows an error and stays on the page when saving fails', async () => {
    mockedUploadFile.mockRejectedValue({ status: 500, message: 'Could not save documents.' })
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)
    await user.click(screen.getByRole('button', { name: 'Save documents' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not save documents.')
    expect(screen.queryByText('Documents page stub')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save documents' })).toBeEnabled()
  })
})
