import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { FileDropzone } from '@/components/upload/FileDropzone'

function makeFile(name = 'note.txt'): File {
  return new File(['hello'], name, { type: 'text/plain' })
}

function getDropzone() {
  return screen.getByRole('button', { name: /Upload clinical note files/ })
}

describe('FileDropzone', () => {
  it('advertises supported formats in its accessible name', () => {
    render(<FileDropzone onFilesSelected={vi.fn()} />)

    expect(getDropzone()).toHaveAccessibleName(/Supported formats: \.txt, \.pdf, \.csv/)
  })

  it('opens the native file picker when clicked', async () => {
    const user = userEvent.setup()
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(() => {})
    render(<FileDropzone onFilesSelected={vi.fn()} />)

    await user.click(getDropzone())

    expect(clickSpy).toHaveBeenCalledTimes(1)
    clickSpy.mockRestore()
  })

  it('opens the native file picker on Enter or Space when focused (keyboard operable)', async () => {
    const user = userEvent.setup()
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(() => {})
    render(<FileDropzone onFilesSelected={vi.fn()} />)

    getDropzone().focus()
    await user.keyboard('[Enter]')
    await user.keyboard('[Space]')

    expect(clickSpy).toHaveBeenCalledTimes(2)
    clickSpy.mockRestore()
  })

  it('calls onFilesSelected with the chosen files when selected via the file input', async () => {
    const onFilesSelected = vi.fn()
    const user = userEvent.setup()
    render(<FileDropzone onFilesSelected={onFilesSelected} />)

    const file = makeFile()
    await user.upload(screen.getByTestId('file-input'), file)

    expect(onFilesSelected).toHaveBeenCalledWith([file])
  })

  it('calls onFilesSelected with the dropped files on drag-and-drop', () => {
    const onFilesSelected = vi.fn()
    render(<FileDropzone onFilesSelected={onFilesSelected} />)

    const file = makeFile('dropped.pdf')
    fireEvent.drop(getDropzone(), { dataTransfer: { files: [file] } })

    expect(onFilesSelected).toHaveBeenCalledWith([file])
  })

  it('has no aria-describedby when there is no error', () => {
    render(<FileDropzone onFilesSelected={vi.fn()} />)

    expect(getDropzone()).not.toHaveAttribute('aria-describedby')
  })

  it('links to the given errorId via aria-describedby when a file-selection error is present', () => {
    render(<FileDropzone onFilesSelected={vi.fn()} errorId="upload-file-error" />)

    expect(getDropzone()).toHaveAttribute('aria-describedby', 'upload-file-error')
  })
})
