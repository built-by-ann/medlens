import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { UploadPage } from '@/pages/UploadPage'
import { fileItemKey, noteItemKey, useCreateAnalysis } from '@/hooks/useCreateAnalysis'
import { getPatient } from '@/api/patients'
import type { Patient } from '@/types/api'

vi.mock('@/hooks/useCreateAnalysis', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/hooks/useCreateAnalysis')>()

  return {
    ...actual,
    useCreateAnalysis: vi.fn(),
  }
})

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    getPatient: vi.fn(),
  }
})

const mockedUseCreateAnalysis = vi.mocked(useCreateAnalysis)
const mockedGetPatient = vi.mocked(getPatient)
const submit = vi.fn()
const invalidateItem = vi.fn()

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
    submit.mockReset()
    invalidateItem.mockReset()
    mockedGetPatient.mockReset()
    mockedGetPatient.mockResolvedValue(patient)
    mockedUseCreateAnalysis.mockReturnValue({
      isSubmitting: false,
      error: null,
      failedItemLabel: null,
      submit,
      invalidateItem,
    })
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

  it('removes a selected file and invalidates its cached upload', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)
    expect(screen.getByText(/note\.txt/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Remove note.txt' }))

    expect(screen.queryByText(/note\.txt/)).not.toBeInTheDocument()
    expect(invalidateItem).toHaveBeenCalledWith(fileItemKey(0))
  })

  it('changing a selected file’s document type invalidates its cached upload', async () => {
    const user = userEvent.setup()
    const { container } = renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)

    await user.selectOptions(getById(container, 'file-doctype-0'), 'medication_list')

    expect(invalidateItem).toHaveBeenCalledWith(fileItemKey(0))
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

  it('lets a manually entered note be created with a non-default document type', async () => {
    submit.mockResolvedValue(1)
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    await user.type(screen.getByLabelText('Note text'), 'Metformin 500mg, Lisinopril 10mg')
    await user.selectOptions(screen.getByLabelText('Document type'), 'medication_list')
    await user.click(screen.getByRole('button', { name: 'Add note' }))

    await user.click(screen.getByRole('button', { name: 'Start Analysis' }))

    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith({
        files: [],
        notes: [
          {
            id: 0,
            title: '',
            rawText: 'Metformin 500mg, Lisinopril 10mg',
            documentType: 'medication_list',
          },
        ],
      }),
    )
  })

  it('removes a manually entered note and invalidates its cached upload', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    await user.type(screen.getByLabelText('Note text'), 'Some note text')
    await user.click(screen.getByRole('button', { name: 'Add note' }))
    expect(screen.getByText('Some note text')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Remove Note 1/ }))

    expect(screen.queryByText('Some note text')).not.toBeInTheDocument()
    expect(invalidateItem).toHaveBeenCalledWith(noteItemKey(0))
  })

  it('editing a note’s text invalidates its cached upload', async () => {
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
    expect(invalidateItem).toHaveBeenCalledWith(noteItemKey(0))
  })

  it('blocks submission when nothing has been added', async () => {
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    await user.click(screen.getByRole('button', { name: 'Start Analysis' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Add at least one file or note before starting an analysis.',
    )
    expect(submit).not.toHaveBeenCalled()
  })

  it('submits the added file and note together and shows a success panel', async () => {
    submit.mockResolvedValue(42)
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await user.upload(getFileInput(), file)

    await user.type(screen.getByLabelText('Note text'), 'Pasted note text')
    await user.click(screen.getByRole('button', { name: 'Add note' }))

    await user.click(screen.getByRole('button', { name: 'Start Analysis' }))

    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith({
        files: [{ id: 0, file, documentType: 'visit_note' }],
        notes: [{ id: 0, title: '', rawText: 'Pasted note text', documentType: 'visit_note' }],
      }),
    )

    expect(await screen.findByRole('status')).toHaveTextContent('Analysis started successfully')
    expect(screen.getByRole('link', { name: 'View analysis' })).toHaveAttribute(
      'href',
      '/patients/7/analyses/42',
    )
    expect(screen.getByRole('link', { name: 'View documents' })).toHaveAttribute(
      'href',
      '/patients/7#documents-heading',
    )
    expect(screen.getByRole('link', { name: 'Back to patient' })).toHaveAttribute(
      'href',
      '/patients/7',
    )
  })

  it('lets the user start a fresh upload after a successful submission', async () => {
    submit.mockResolvedValue(42)
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    await user.type(screen.getByLabelText('Note text'), 'Pasted note text')
    await user.click(screen.getByRole('button', { name: 'Add note' }))
    await user.click(screen.getByRole('button', { name: 'Start Analysis' }))

    await screen.findByRole('status')
    await user.click(screen.getByRole('button', { name: 'Upload another' }))

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start Analysis' })).toBeInTheDocument()
    expect(screen.queryByText('Pasted note text')).not.toBeInTheDocument()
  })

  it('shows the submission error and which item failed, without a success panel', async () => {
    submit.mockRejectedValue(new Error('failed'))
    mockedUseCreateAnalysis.mockReturnValue({
      isSubmitting: false,
      error: 'Something went wrong on the server.',
      failedItemLabel: 'note.txt',
      submit,
      invalidateItem,
    })
    const user = userEvent.setup()
    renderUploadPage()

    await screen.findByRole('heading', { name: /Upload documents for Jane Doe/ })

    await user.type(screen.getByLabelText('Note text'), 'Some text')
    await user.click(screen.getByRole('button', { name: 'Add note' }))
    await user.click(screen.getByRole('button', { name: 'Start Analysis' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Something went wrong on the server.')
    expect(alert).toHaveTextContent('note.txt')
    expect(screen.queryByRole('link', { name: 'View analysis' })).not.toBeInTheDocument()
  })

  it('shows a loading state and disables the submit button while submitting', async () => {
    mockedUseCreateAnalysis.mockReturnValue({
      isSubmitting: true,
      error: null,
      failedItemLabel: null,
      submit,
      invalidateItem,
    })
    renderUploadPage()

    expect(await screen.findByRole('button', { name: 'Starting analysis...' })).toBeDisabled()
  })
})
