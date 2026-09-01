import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MedicationCsvUpload } from '@/components/medications/MedicationCsvUpload'
import type { MedicationCsvImportError } from '@/api/medications'
import type { MedicationImportSummary } from '@/types/api'

function csvFile(name = 'medications.csv', content = 'medication_name,dose\nLisinopril,10 mg\n') {
  return new File([content], name, { type: 'text/csv' })
}

function getFileInput(): HTMLInputElement {
  return screen.getByTestId('csv-file-input')
}

function getDropzone() {
  return screen.getByRole('button', { name: /Upload a CSV file/ })
}

describe('MedicationCsvUpload', () => {
  let createObjectURL: ReturnType<typeof vi.fn>
  let revokeObjectURL: ReturnType<typeof vi.fn>

  beforeEach(() => {
    createObjectURL = vi.fn(() => 'blob:mock-url')
    revokeObjectURL = vi.fn()
    // jsdom does not implement these; stubbed locally since only the
    // sample-CSV download in this one component needs them.
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL })
  })

  it('disables the import button until a file is selected', () => {
    render(<MedicationCsvUpload onImport={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Import CSV' })).toBeDisabled()
  })

  it('is a keyboard-focusable dropzone, matching the Upload page pattern', () => {
    render(<MedicationCsvUpload onImport={vi.fn()} />)

    expect(getDropzone()).toHaveAttribute('tabIndex', '0')
  })

  it('rejects an unsupported file type dropped onto the zone, with a visible error', async () => {
    // A real OS file picker constrained by `accept` would never offer this
    // file in the first place, and userEvent.upload() respects `accept`
    // the same way, so a drop is used here instead, exactly like
    // UploadPage's own dropzone test for the same reason.
    render(<MedicationCsvUpload onImport={vi.fn()} />)

    const file = new File(['not a csv'], 'medications.txt', { type: 'text/plain' })
    fireEvent.drop(getDropzone(), { dataTransfer: { files: [file] } })

    expect(await screen.findByRole('alert')).toHaveTextContent('not a supported file type')
    expect(screen.getByRole('button', { name: 'Import CSV' })).toBeDisabled()
  })

  it('rejects an empty file', async () => {
    const user = userEvent.setup()
    render(<MedicationCsvUpload onImport={vi.fn()} />)

    const file = new File([], 'empty.csv', { type: 'text/csv' })
    await user.upload(getFileInput(), file)

    expect(await screen.findByRole('alert')).toHaveTextContent('is empty')
    expect(screen.getByRole('button', { name: 'Import CSV' })).toBeDisabled()
  })

  it('accepts a valid CSV file selected via the file picker and shows its name', async () => {
    const user = userEvent.setup()
    render(<MedicationCsvUpload onImport={vi.fn()} />)

    await user.upload(getFileInput(), csvFile())

    expect(screen.getByText('medications.csv')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Import CSV' })).toBeEnabled()
  })

  it('accepts a valid CSV file dropped onto the zone', async () => {
    render(<MedicationCsvUpload onImport={vi.fn()} />)

    fireEvent.drop(getDropzone(), { dataTransfer: { files: [csvFile()] } })

    expect(await screen.findByText('medications.csv')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Import CSV' })).toBeEnabled()
  })

  it('clears the selected file', async () => {
    const user = userEvent.setup()
    render(<MedicationCsvUpload onImport={vi.fn()} />)

    await user.upload(getFileInput(), csvFile())
    await user.click(screen.getByRole('button', { name: 'Remove file' }))

    expect(screen.queryByText('medications.csv')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Import CSV' })).toBeDisabled()
  })

  it('replaces a selected file with a new one', async () => {
    const user = userEvent.setup()
    render(<MedicationCsvUpload onImport={vi.fn()} />)

    await user.upload(getFileInput(), csvFile('first.csv'))
    await user.upload(getFileInput(), csvFile('second.csv'))

    expect(screen.queryByText('first.csv')).not.toBeInTheDocument()
    expect(screen.getByText('second.csv')).toBeInTheDocument()
  })

  it('imports the selected file and shows the success count', async () => {
    const summary: MedicationImportSummary = {
      rows_processed: 2,
      medications_created: 2,
      blank_rows_ignored: 0,
    }
    const onImport = vi.fn().mockResolvedValue(summary)
    const user = userEvent.setup()
    render(<MedicationCsvUpload onImport={onImport} />)

    await user.upload(getFileInput(), csvFile())
    await user.click(screen.getByRole('button', { name: 'Import CSV' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Imported 2 of 2 rows')
    expect(onImport).toHaveBeenCalledWith(expect.any(File))
    // Clears the file after success.
    expect(screen.queryByText('medications.csv')).not.toBeInTheDocument()
  })

  it('mentions blank rows skipped when present', async () => {
    const summary: MedicationImportSummary = {
      rows_processed: 3,
      medications_created: 2,
      blank_rows_ignored: 1,
    }
    const onImport = vi.fn().mockResolvedValue(summary)
    const user = userEvent.setup()
    render(<MedicationCsvUpload onImport={onImport} />)

    await user.upload(getFileInput(), csvFile())
    await user.click(screen.getByRole('button', { name: 'Import CSV' }))

    expect(await screen.findByRole('status')).toHaveTextContent('1 blank row skipped')
  })

  it('shows a disabled, loading state while importing and prevents duplicate submissions', async () => {
    let resolveImport: (summary: MedicationImportSummary) => void = () => {}
    const onImport = vi.fn(
      () =>
        new Promise<MedicationImportSummary>((resolve) => {
          resolveImport = resolve
        }),
    )
    const user = userEvent.setup()
    render(<MedicationCsvUpload onImport={onImport} />)

    await user.upload(getFileInput(), csvFile())
    const importButton = screen.getByRole('button', { name: 'Import CSV' })
    await user.click(importButton)
    await user.click(importButton)

    expect(await screen.findByRole('button', { name: 'Importing...' })).toBeDisabled()
    expect(onImport).toHaveBeenCalledTimes(1)

    resolveImport({ rows_processed: 1, medications_created: 1, blank_rows_ignored: 0 })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Import CSV' })).toBeDisabled())
  })

  it('shows a file-level error message from the API', async () => {
    const onImport = vi.fn().mockRejectedValue({
      status: 422,
      message: 'Only .csv or text/csv files are supported',
    } satisfies MedicationCsvImportError)
    const user = userEvent.setup()
    render(<MedicationCsvUpload onImport={onImport} />)

    await user.upload(getFileInput(), csvFile())
    await user.click(screen.getByRole('button', { name: 'Import CSV' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Only .csv or text/csv files are supported',
    )
  })

  it('shows row-level validation errors distinctly, preserving row numbers', async () => {
    const onImport = vi.fn().mockRejectedValue({
      status: 422,
      message: 'CSV import failed validation. No medications were created.',
      rowErrors: [
        { row: 3, errors: [{ field: 'dose', message: 'String should have at least 1 character' }] },
      ],
    } satisfies MedicationCsvImportError)
    const user = userEvent.setup()
    render(<MedicationCsvUpload onImport={onImport} />)

    await user.upload(getFileInput(), csvFile())
    await user.click(screen.getByRole('button', { name: 'Import CSV' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('No medications were created')
    expect(alert).toHaveTextContent('Row 3')
    expect(alert).toHaveTextContent('dose - String should have at least 1 character')
  })

  it('re-enables the button after a failed import, and does not clear the file', async () => {
    const onImport = vi.fn().mockRejectedValue({ status: 500, message: 'Server error.' })
    const user = userEvent.setup()
    render(<MedicationCsvUpload onImport={onImport} />)

    await user.upload(getFileInput(), csvFile())
    await user.click(screen.getByRole('button', { name: 'Import CSV' }))

    await screen.findByRole('alert')
    expect(screen.getByText('medications.csv')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Import CSV' })).toBeEnabled()
  })

  it('has a keyboard-accessible sample CSV download that does not require a file to be selected', async () => {
    const user = userEvent.setup()
    render(<MedicationCsvUpload onImport={vi.fn()} />)

    await user.tab()
    expect(screen.getByRole('button', { name: 'Download a sample CSV' })).toHaveFocus()

    await user.keyboard('{Enter}')
    expect(createObjectURL).toHaveBeenCalledWith(expect.any(Blob))

    await user.tab()
    expect(getDropzone()).toHaveFocus()
  })

  it('associates the format instructions and file errors with the dropzone', async () => {
    render(<MedicationCsvUpload onImport={vi.fn()} />)

    const dropzone = getDropzone()
    const describedBy = dropzone.getAttribute('aria-describedby') ?? ''
    const [descriptionId] = describedBy.split(' ')
    expect(descriptionId).toBeTruthy()
    expect(document.getElementById(descriptionId ?? '')).toHaveTextContent('medication_name')

    fireEvent.drop(dropzone, {
      dataTransfer: { files: [new File(['x'], 'bad.txt', { type: 'text/plain' })] },
    })
    const alert = await screen.findByRole('alert')
    expect(dropzone.getAttribute('aria-describedby')).toContain(alert.id)
  })
})
