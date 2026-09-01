import { Card } from '@/components/common/Card'
import { Input } from '@/components/common/Input'
import { DocumentTypeSelect } from '@/components/upload/DocumentTypeSelect'
import { deriveTitleFromFileName } from '@/api/clinicalDocuments'
import { findDuplicateExistingTitle } from '@/utils/queuedFiles'
import type { QueuedFile } from '@/hooks/useCreateAnalysis'

interface UploadedFileListProps {
  files: QueuedFile[]
  onRemove: (id: number) => void
  onDocumentTypeChange: (id: number, documentType: string) => void
  // Unset until a provider edits it, e.g. to resolve a same-name collision
  // (see existingDocumentTitles below); the document is titled from the
  // filename on upload otherwise.
  onTitleChange: (id: number, title: string) => void
  // Titles of documents the patient already has on file. Set only by
  // CreateAnalysisPage, which already has this list loaded to render
  // Existing Documents; UploadPage doesn't fetch it, so this stays unset
  // there and no warning renders. Purely a heads-up (same filename as
  // something already saved): the file stays queued either way, nothing is
  // blocked.
  existingDocumentTitles?: string[]
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function UploadedFileList({
  files,
  onRemove,
  onDocumentTypeChange,
  onTitleChange,
  existingDocumentTitles,
}: UploadedFileListProps) {
  if (files.length === 0) {
    return null
  }

  return (
    <ul className="flex flex-col gap-3">
      {files.map((queued) => {
        const duplicateOfTitle = existingDocumentTitles
          ? findDuplicateExistingTitle(queued, existingDocumentTitles)
          : undefined

        return (
          <li key={queued.id}>
            <Card className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <span className="text-sm font-medium text-foreground">File</span>
                <p className="truncate text-sm text-foreground">
                  {queued.file.name}{' '}
                  <span className="text-muted">({formatFileSize(queued.file.size)})</span>
                </p>
                {duplicateOfTitle && (
                  <p className="text-xs text-warning" role="status">
                    A document named "{duplicateOfTitle}" already exists for this patient.
                  </p>
                )}
              </div>
              <Input
                label="Title (optional)"
                value={queued.title ?? ''}
                onChange={(event) => onTitleChange(queued.id, event.target.value)}
                placeholder={deriveTitleFromFileName(queued.file.name)}
              />
              <DocumentTypeSelect
                id={`file-doctype-${queued.id}`}
                value={queued.documentType}
                onChange={(documentType) => onDocumentTypeChange(queued.id, documentType)}
              />
              <button
                type="button"
                onClick={() => onRemove(queued.id)}
                aria-label={`Remove ${queued.file.name}`}
                className="self-start rounded-md px-2 py-1 text-xs font-medium text-danger hover:bg-danger/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
              >
                Remove
              </button>
            </Card>
          </li>
        )
      })}
    </ul>
  )
}
