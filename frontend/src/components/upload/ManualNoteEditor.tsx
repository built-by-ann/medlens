import { useState } from 'react'
import { Card } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { DocumentTypeSelect } from '@/components/upload/DocumentTypeSelect'
import { DEFAULT_DOCUMENT_TYPE } from '@/api/clinicalDocuments'

interface ManualNoteEditorProps {
  onAdd: (note: { title: string; rawText: string; documentType: string }) => void
}

export function ManualNoteEditor({ onAdd }: ManualNoteEditorProps) {
  const [title, setTitle] = useState('')
  const [rawText, setRawText] = useState('')
  const [documentType, setDocumentType] = useState(DEFAULT_DOCUMENT_TYPE)

  function handleAdd() {
    if (!rawText.trim()) {
      return
    }

    onAdd({ title: title.trim(), rawText: rawText.trim(), documentType })
    setTitle('')
    setRawText('')
    setDocumentType(DEFAULT_DOCUMENT_TYPE)
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
        <label htmlFor="new-note-text" className="text-sm font-medium text-slate-700">
          Note text
        </label>
        <textarea
          id="new-note-text"
          value={rawText}
          onChange={(event) => setRawText(event.target.value)}
          rows={6}
          placeholder="Paste or type the clinical note text here"
          className="rounded-md border border-slate-300 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        />
      </div>
      <DocumentTypeSelect id="new-note-doctype" value={documentType} onChange={setDocumentType} />
      <Button onClick={handleAdd} disabled={!rawText.trim()} className="self-start">
        Add note
      </Button>
    </Card>
  )
}
