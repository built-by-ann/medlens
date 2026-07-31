import { useState } from 'react'
import { Card } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { FormError } from '@/components/common/FormError'
import { DocumentTypeSelect } from '@/components/upload/DocumentTypeSelect'
import { documentTypeLabel } from '@/api/clinicalDocuments'

export interface DraftNote {
  id: number
  title: string
  rawText: string
  documentType: string
}

interface NoteCardProps {
  note: DraftNote
  // 1-based position of this note among the currently queued notes, used
  // only for the untitled fallback name below. Deliberately not note.id:
  // that's a counter that only ever increases (Issue #164), so after
  // removing an earlier note it would skip numbers instead of renumbering,
  // and wouldn't match the title useCreateAnalysis itself falls back to at
  // submit time (which numbers by position in the array, not by id).
  position: number
  onUpdate: (id: number, note: { title: string; rawText: string; documentType: string }) => void
  onRemove: (id: number) => void
}

const TEXT_ERROR_ID_PREFIX = 'note-text-error'

export function NoteCard({ note, position, onUpdate, onRemove }: NoteCardProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [draftTitle, setDraftTitle] = useState(note.title)
  const [draftText, setDraftText] = useState(note.rawText)
  const [draftDocumentType, setDraftDocumentType] = useState(note.documentType)
  // Only set once Save is clicked with empty text - matching every other
  // form in the app (validate on submit, not disable the button with no
  // explanation of why).
  const [showTextError, setShowTextError] = useState(false)
  const textErrorId = `${TEXT_ERROR_ID_PREFIX}-${note.id}`

  function startEditing() {
    setDraftTitle(note.title)
    setDraftText(note.rawText)
    setDraftDocumentType(note.documentType)
    setShowTextError(false)
    setIsEditing(true)
  }

  function handleDraftTextChange(value: string) {
    setDraftText(value)
    if (showTextError && value.trim()) {
      setShowTextError(false)
    }
  }

  function saveEdit() {
    if (!draftText.trim()) {
      setShowTextError(true)
      return
    }

    onUpdate(note.id, {
      title: draftTitle.trim(),
      rawText: draftText.trim(),
      documentType: draftDocumentType,
    })
    setIsEditing(false)
  }

  const displayTitle = note.title || `Note ${position}`

  if (isEditing) {
    return (
      <Card className="flex flex-col gap-3">
        <Input
          label="Title (optional)"
          value={draftTitle}
          onChange={(event) => setDraftTitle(event.target.value)}
        />
        <div className="flex flex-col gap-1">
          <label htmlFor={`note-text-${note.id}`} className="text-sm font-medium text-slate-700">
            Note text
          </label>
          <textarea
            id={`note-text-${note.id}`}
            value={draftText}
            onChange={(event) => handleDraftTextChange(event.target.value)}
            rows={6}
            aria-invalid={showTextError ? true : undefined}
            aria-describedby={showTextError ? textErrorId : undefined}
            className={`w-full rounded-md border px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 ${
              showTextError ? 'border-red-500' : 'border-slate-300'
            }`}
          />
          {showTextError && <FormError id={textErrorId} message="Note text is required." />}
        </div>
        <DocumentTypeSelect
          id={`note-doctype-${note.id}`}
          value={draftDocumentType}
          onChange={setDraftDocumentType}
        />
        <div className="flex flex-wrap gap-2">
          <Button onClick={saveEdit}>Save</Button>
          <button
            type="button"
            onClick={() => setIsEditing(false)}
            className="cursor-pointer rounded-md px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            Cancel
          </button>
        </div>
      </Card>
    )
  }

  return (
    <Card className="flex flex-col gap-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="truncate text-sm font-semibold text-slate-900">{displayTitle}</h4>
          <p className="text-xs text-slate-500">{documentTypeLabel(note.documentType)}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            type="button"
            onClick={startEditing}
            className="cursor-pointer rounded-md px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            Edit
          </button>
          <button
            type="button"
            onClick={() => onRemove(note.id)}
            aria-label={`Remove ${displayTitle}`}
            className="cursor-pointer rounded-md px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            Remove
          </button>
        </div>
      </div>
      <p className="line-clamp-3 text-sm text-slate-600">{note.rawText}</p>
    </Card>
  )
}
