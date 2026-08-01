import { useState } from 'react'
import { Card } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { FormError } from '@/components/common/FormError'
import { DocumentTypeSelect } from '@/components/upload/DocumentTypeSelect'
import { DEFAULT_DOCUMENT_TYPE } from '@/api/clinicalDocuments'

interface ManualNoteEditorProps {
  onAdd: (note: { title: string; rawText: string; documentType: string }) => void
}

const TEXT_ERROR_ID = 'new-note-text-error'

export function ManualNoteEditor({ onAdd }: ManualNoteEditorProps) {
  const [title, setTitle] = useState('')
  const [rawText, setRawText] = useState('')
  const [documentType, setDocumentType] = useState(DEFAULT_DOCUMENT_TYPE)
  // Only set once Add note is clicked with empty text - matching every
  // other form in the app (validate on submit, not disable the button with
  // no explanation of why).
  const [showTextError, setShowTextError] = useState(false)

  function handleRawTextChange(value: string) {
    setRawText(value)
    if (showTextError && value.trim()) {
      setShowTextError(false)
    }
  }

  function handleAdd() {
    if (!rawText.trim()) {
      setShowTextError(true)
      return
    }

    onAdd({ title: title.trim(), rawText: rawText.trim(), documentType })
    setTitle('')
    setRawText('')
    setDocumentType(DEFAULT_DOCUMENT_TYPE)
    setShowTextError(false)
  }

  return (
    <Card className="flex flex-col gap-3">
      <Input
        label="Title (optional)"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        placeholder="e.g. Visit note, March 3"
      />
      <div className="flex flex-col gap-1">
        <label htmlFor="new-note-text" className="text-sm font-medium text-foreground">
          Note text
        </label>
        <textarea
          id="new-note-text"
          value={rawText}
          onChange={(event) => handleRawTextChange(event.target.value)}
          rows={6}
          placeholder="Paste or type the clinical note text here"
          aria-invalid={showTextError ? true : undefined}
          aria-describedby={showTextError ? TEXT_ERROR_ID : undefined}
          className={`w-full rounded-md border px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${
            showTextError ? 'border-danger' : 'border-border'
          }`}
        />
        {showTextError && <FormError id={TEXT_ERROR_ID} message="Note text is required." />}
      </div>
      <DocumentTypeSelect id="new-note-doctype" value={documentType} onChange={setDocumentType} />
      <Button onClick={handleAdd} className="self-start">
        Add note
      </Button>
    </Card>
  )
}
