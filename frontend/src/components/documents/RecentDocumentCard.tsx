import { useState } from 'react'
import { Card } from '@/components/common/Card'
import { documentTypeLabel } from '@/api/clinicalDocuments'
import type { ClinicalDocument } from '@/types/api'

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

interface RecentDocumentCardProps {
  document: ClinicalDocument
}

// A compact, glance-and-go preview for Patient Overview - the whole card
// toggles an inline expand/collapse to view the document's extracted text,
// the same interaction ClinicalDocumentCard's "View" button offers on the
// full Clinical Documents page, just without a separate Delete action here.
export function RecentDocumentCard({ document }: RecentDocumentCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const contentId = `recent-document-content-${document.id}`

  return (
    <Card className="p-0">
      <button
        type="button"
        onClick={() => setIsExpanded((current) => !current)}
        aria-expanded={isExpanded}
        aria-controls={contentId}
        aria-label={`${isExpanded ? 'Hide' : 'View'} ${document.title}`}
        className="flex w-full cursor-pointer flex-col gap-1 rounded-lg p-4 text-left hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      >
        <h4 className="text-sm font-semibold text-slate-900">{document.title}</h4>
        <p className="text-xs text-slate-500">
          {documentTypeLabel(document.document_type)} · {formatDate(document.created_at)}
        </p>
      </button>

      {isExpanded && (
        <p
          id={contentId}
          className="max-h-64 overflow-y-auto rounded-b-lg bg-slate-50 p-4 text-sm whitespace-pre-wrap text-slate-700"
        >
          {document.raw_text}
        </p>
      )}
    </Card>
  )
}
