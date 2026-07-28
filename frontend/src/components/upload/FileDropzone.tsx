import { useRef, useState, type ChangeEvent, type DragEvent, type KeyboardEvent } from 'react'
import { SUPPORTED_FILE_EXTENSIONS } from '@/api/clinicalDocuments'
import { cn } from '@/utils/cn'

interface FileDropzoneProps {
  onFilesSelected: (files: File[]) => void
}

const ACCEPT_ATTRIBUTE = [...SUPPORTED_FILE_EXTENSIONS, 'text/plain', 'application/pdf'].join(',')

export function FileDropzone({ onFilesSelected }: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDraggingOver, setIsDraggingOver] = useState(false)

  function openFilePicker() {
    inputRef.current?.click()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      openFilePicker()
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setIsDraggingOver(false)
    onFilesSelected(Array.from(event.dataTransfer.files))
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files) {
      onFilesSelected(Array.from(event.target.files))
    }

    // Reset so selecting the exact same file again still fires onChange.
    event.target.value = ''
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`Upload clinical note files. Drag and drop, or activate to browse. Supported formats: ${SUPPORTED_FILE_EXTENSIONS.join(', ')}.`}
      onClick={openFilePicker}
      onKeyDown={handleKeyDown}
      onDragOver={(event) => {
        event.preventDefault()
        setIsDraggingOver(true)
      }}
      onDragLeave={() => setIsDraggingOver(false)}
      onDrop={handleDrop}
      className={cn(
        'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-10 text-center transition-colors',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600',
        isDraggingOver ? 'border-blue-500 bg-blue-50' : 'border-slate-300 hover:border-slate-400',
      )}
    >
      <p className="text-sm font-medium text-slate-700">
        Drag and drop files here, or click to browse
      </p>
      <p className="text-xs text-slate-500">
        Supported formats: {SUPPORTED_FILE_EXTENSIONS.join(', ')}
      </p>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPT_ATTRIBUTE}
        onChange={handleInputChange}
        tabIndex={-1}
        aria-hidden="true"
        data-testid="file-input"
        className="sr-only"
      />
    </div>
  )
}
