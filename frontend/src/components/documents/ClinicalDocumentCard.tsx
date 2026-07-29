import { useState } from 'react'
import { Card } from '@/components/common/Card'
import { documentTypeLabel } from '@/api/clinicalDocuments'
import type { ApiError } from '@/api/client'
import type { ClinicalDocument } from '@/types/api'

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

// file_type is "manual_entry" for pasted notes, or the real upload format
// ("txt"/"pdf") for uploaded files - there is no separate "source" field to
// read, so this is the one place that distinction is surfaced to the user.
const FILE_TYPE_LABELS: Record<string, string> = {
  manual_entry: 'Pasted note',
  txt: 'Uploaded .txt file',
  pdf: 'Uploaded .pdf file',
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
        <div>
          <h4 className="text-sm font-semibold text-slate-900">{document.title}</h4>
          <p className="text-xs text-slate-500">
            {documentTypeLabel(document.document_type)} · {formatDate(document.created_at)}
            {document.file_type &&
              ` · ${FILE_TYPE_LABELS[document.file_type] ?? document.file_type}`}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => setIsExpanded((current) => !current)}
            aria-expanded={isExpanded}
            aria-controls={contentId}
            className="cursor-pointer rounded-md px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            {isExpanded ? 'Hide' : 'View'}
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={isDeleting}
            aria-label={`Delete ${document.title}`}
            className="cursor-pointer rounded-md px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isDeleting ? 'Removing...' : 'Delete'}
          </button>
        </div>
      </div>

      {isExpanded && (
        <p
          id={contentId}
          className="max-h-64 overflow-y-auto rounded-md bg-slate-50 p-3 text-sm whitespace-pre-wrap text-slate-700"
        >
          {document.raw_text}
        </p>
      )}

      {deleteError && (
        <p role="alert" className="text-sm text-red-600">
          {deleteError}
        </p>
      )}
    </Card>
  )
}
