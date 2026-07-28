import { DocumentTypeSelect } from '@/components/upload/DocumentTypeSelect'
import type { QueuedFile } from '@/hooks/useCreateAnalysis'

interface UploadedFileListProps {
  files: QueuedFile[]
  onRemove: (id: number) => void
  onDocumentTypeChange: (id: number, documentType: string) => void
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

export function UploadedFileList({ files, onRemove, onDocumentTypeChange }: UploadedFileListProps) {
  if (files.length === 0) {
    return null
  }

  return (
    <ul className="flex flex-col gap-3">
      {files.map((queued) => (
        <li
          key={queued.id}
          className="flex flex-col gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm sm:flex-row sm:items-end sm:justify-between"
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
            <span className="truncate">
              {queued.file.name}{' '}
              <span className="text-slate-400">({formatFileSize(queued.file.size)})</span>
            </span>
            <div className="w-48">
              <DocumentTypeSelect
                id={`file-doctype-${queued.id}`}
                value={queued.documentType}
                onChange={(documentType) => onDocumentTypeChange(queued.id, documentType)}
              />
            </div>
          </div>
          <button
            type="button"
            onClick={() => onRemove(queued.id)}
            aria-label={`Remove ${queued.file.name}`}
            className="shrink-0 self-start rounded-md px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 sm:self-auto"
          >
            Remove
          </button>
        </li>
      ))}
    </ul>
  )
}
