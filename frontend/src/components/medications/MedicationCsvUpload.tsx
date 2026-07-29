import {
  useId,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
} from 'react'
import { Button } from '@/components/common/Button'
import { Card } from '@/components/common/Card'
import { downloadSampleMedicationCsv } from '@/components/medications/sampleMedicationCsv'
import { cn } from '@/utils/cn'
import type { MedicationCsvImportError } from '@/api/medications'
import type { MedicationImportSummary } from '@/types/api'

function isSupportedCsvFile(file: File): boolean {
  const name = file.name.toLowerCase()
  return name.endsWith('.csv') || file.type === 'text/csv'
}

type ImportOutcome =
  | { type: 'success'; summary: MedicationImportSummary }
  | { type: 'error'; message: string; rowErrors?: MedicationCsvImportError['rowErrors'] }

interface MedicationCsvUploadProps {
  onImport: (file: File) => Promise<MedicationImportSummary>
}

/**
 * A dedicated section on PatientMedicationsPage, not a modal or a
 * collapsible - the page already shows a single, always-visible add-one
 * form (MedicationForm) below the list, so this follows the same
 * always-visible pattern rather than introducing a new interaction
 * paradigm for what is, at heart, another way to add medications.
 *
 * The file-selection control mirrors FileDropzone (components/upload/) -
 * same drag-and-drop-plus-click-to-browse box, same keyboard handling, same
 * hidden-native-input approach - so the two file upload experiences in this
 * app look and behave the same way. It's a separate, single-file
 * implementation rather than a shared component: FileDropzone's own
 * accept list, `multiple`, and result handling are specific to Upload's
 * multi-document queue and already have their own tests, and this one adds
 * CSV-specific validation (type, empty file) FileDropzone has no equivalent
 * of.
 */
export function MedicationCsvUpload({ onImport }: MedicationCsvUploadProps) {
  const inputId = useId()
  const descriptionId = `${inputId}-description`
  const fileErrorId = `${inputId}-file-error`
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [isDraggingOver, setIsDraggingOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [isImporting, setIsImporting] = useState(false)
  const [outcome, setOutcome] = useState<ImportOutcome | null>(null)

  function openFilePicker() {
    if (isImporting) return
    fileInputRef.current?.click()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      openFilePicker()
    }
  }

  function handleFile(file: File | null) {
    setOutcome(null)

    if (!file) {
      setSelectedFile(null)
      setFileError(null)
      return
    }

    if (!isSupportedCsvFile(file)) {
      setSelectedFile(null)
      setFileError(`"${file.name}" is not a supported file type. Choose a .csv file.`)
      return
    }

    if (file.size === 0) {
      setSelectedFile(null)
      setFileError(`"${file.name}" is empty.`)
      return
    }

    setFileError(null)
    setSelectedFile(file)
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    handleFile(event.target.files?.[0] ?? null)
    // Reset so selecting the exact same file again still fires onChange.
    event.target.value = ''
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setIsDraggingOver(false)
    if (isImporting) return
    handleFile(event.dataTransfer.files[0] ?? null)
  }

  function clearSelectedFile() {
    setSelectedFile(null)
    setFileError(null)
    setOutcome(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  async function handleImport() {
    if (!selectedFile || isImporting) return

    setIsImporting(true)
    setOutcome(null)

    try {
      const summary = await onImport(selectedFile)
      setOutcome({ type: 'success', summary })
      setSelectedFile(null)
      setFileError(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (error) {
      const csvError = error as MedicationCsvImportError
      setOutcome({ type: 'error', message: csvError.message, rowErrors: csvError.rowErrors })
    } finally {
      setIsImporting(false)
    }
  }

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-semibold text-slate-900">Import medications from CSV</h3>
        <p id={descriptionId} className="text-sm text-slate-600">
          The file needs a header row with <code>medication_name</code>, <code>dose</code>,{' '}
          <code>route</code>, <code>frequency</code>, <code>status</code>, and <code>source</code>.
          An optional <code>notes</code> column is also supported.
        </p>
        <button
          type="button"
          onClick={downloadSampleMedicationCsv}
          className="self-start text-sm text-blue-600 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Download a sample CSV
        </button>
      </div>

      <div className="flex flex-col gap-1">
        <div
          role="button"
          tabIndex={isImporting ? -1 : 0}
          aria-disabled={isImporting}
          aria-label="Upload a CSV file. Drag and drop, or activate to browse. Supported format: .csv."
          aria-describedby={fileError ? `${descriptionId} ${fileErrorId}` : descriptionId}
          onClick={openFilePicker}
          onKeyDown={handleKeyDown}
          onDragOver={(event) => {
            event.preventDefault()
            if (!isImporting) setIsDraggingOver(true)
          }}
          onDragLeave={() => setIsDraggingOver(false)}
          onDrop={handleDrop}
          className={cn(
            'flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors',
            'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600',
            isImporting ? 'cursor-not-allowed border-slate-200 opacity-50' : 'cursor-pointer',
            !isImporting &&
              (isDraggingOver
                ? 'border-blue-500 bg-blue-50'
                : 'border-slate-300 hover:border-slate-400'),
          )}
        >
          <p className="text-sm font-medium text-slate-700">
            Drag and drop a CSV file here, or click to browse
          </p>
          <p className="text-xs text-slate-500">Supported format: .csv</p>
          <input
            ref={fileInputRef}
            id={inputId}
            type="file"
            accept=".csv,text/csv"
            onChange={handleInputChange}
            disabled={isImporting}
            tabIndex={-1}
            aria-hidden="true"
            data-testid="csv-file-input"
            className="sr-only"
          />
        </div>
        {fileError && (
          <p id={fileErrorId} role="alert" className="text-sm text-red-600">
            {fileError}
          </p>
        )}
      </div>

      {selectedFile && (
        <div className="flex flex-wrap items-center gap-3 text-sm text-slate-700">
          <span>
            Selected file: <strong>{selectedFile.name}</strong>
          </span>
          <button
            type="button"
            onClick={clearSelectedFile}
            disabled={isImporting}
            className="text-red-600 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Remove file
          </button>
        </div>
      )}

      {isImporting && (
        <p role="status" className="text-sm text-slate-500">
          Importing {selectedFile?.name}...
        </p>
      )}

      {outcome?.type === 'error' && (
        <div role="alert" className="flex flex-col gap-2 text-sm text-red-600">
          <p>{outcome.message}</p>
          {outcome.rowErrors && outcome.rowErrors.length > 0 && (
            <ul className="flex flex-col gap-1 border-l-2 border-red-200 pl-3">
              {outcome.rowErrors.map((rowError) => (
                <li key={rowError.row}>
                  Row {rowError.row}:{' '}
                  {rowError.errors
                    .map((fieldError) => `${fieldError.field} - ${fieldError.message}`)
                    .join('; ')}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {outcome?.type === 'success' && (
        <p role="status" className="text-sm text-green-700">
          Imported {outcome.summary.medications_created} of {outcome.summary.rows_processed} row
          {outcome.summary.rows_processed === 1 ? '' : 's'}
          {outcome.summary.blank_rows_ignored > 0
            ? ` (${outcome.summary.blank_rows_ignored} blank row${outcome.summary.blank_rows_ignored === 1 ? '' : 's'} skipped)`
            : ''}
          .
        </p>
      )}

      <Button
        type="button"
        onClick={handleImport}
        disabled={!selectedFile || isImporting}
        className="self-start"
      >
        {isImporting ? 'Importing...' : 'Import CSV'}
      </Button>
    </Card>
  )
}
