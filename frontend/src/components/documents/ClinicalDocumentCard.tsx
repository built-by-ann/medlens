import { useState } from 'react'
import { Card } from '@/components/common/Card'
import { FormError } from '@/components/common/FormError'
import { documentTypeLabel } from '@/api/clinicalDocuments'
import type { ApiError } from '@/api/client'
import type { ClinicalDocument } from '@/types/api'

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

function analysisCountLabel(count: number): string {
  if (count === 0) return 'Not yet analyzed'
  return count === 1 ? 'Used in 1 analysis' : `Used in ${count} analyses`
}

// file_type is "manual_entry" for pasted notes, or the real upload format
// ("txt"/"pdf") for uploaded files; there is no separate "source" field to
// read, so this is the one place that distinction is surfaced to the user.
const FILE_TYPE_LABELS: Record<string, string> = {
  manual_entry: 'Pasted note',
  txt: 'Uploaded .txt file',
  pdf: 'Uploaded .pdf file',
  csv: 'Uploaded .csv file',
}

interface ClinicalDocumentCardProps {
  document: ClinicalDocument
  onDelete: (id: number) => Promise<void>
}

export function ClinicalDocumentCard({ document, onDelete }: ClinicalDocumentCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const contentId = `document-content-${document.id}`

  async function handleDelete() {
    if (isDeleting) return

    setIsDeleting(true)
    setDeleteError(null)
    try {
      await onDelete(document.id)
    } catch (error) {
      setDeleteError((error as ApiError).message)
      setIsDeleting(false)
    }
  }

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <button
          type="button"
          onClick={() => setIsExpanded((current) => !current)}
          aria-expanded={isExpanded}
          aria-controls={contentId}
          aria-label={`${isExpanded ? 'Hide' : 'View'} ${document.title}`}
          className="-m-2 min-w-0 flex-1 cursor-pointer rounded-md p-2 text-left hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        >
          <h4 className="truncate text-sm font-semibold text-foreground">{document.title}</h4>
          <p className="text-xs text-muted">
            {documentTypeLabel(document.document_type)} · {formatDate(document.created_at)}
            {document.file_type &&
              ` · ${FILE_TYPE_LABELS[document.file_type] ?? document.file_type}`}
            {' · '}
            {analysisCountLabel(document.analysis_count)}
          </p>
        </button>
        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            type="button"
            onClick={handleDelete}
            disabled={isDeleting}
            aria-label={`Delete ${document.title}`}
            className="cursor-pointer rounded-md px-2 py-1 text-xs font-medium text-danger hover:bg-danger/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isDeleting ? 'Removing...' : 'Delete'}
          </button>
        </div>
      </div>

      {isExpanded && (
        <p
          id={contentId}
          className="max-h-64 overflow-y-auto rounded-md bg-background p-3 text-sm whitespace-pre-wrap text-foreground"
        >
          {document.raw_text}
        </p>
      )}

      {deleteError && <FormError message={deleteError} />}
    </Card>
  )
}
