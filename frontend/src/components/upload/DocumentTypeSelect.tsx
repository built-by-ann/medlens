import { DOCUMENT_TYPES } from '@/api/clinicalDocuments'

interface DocumentTypeSelectProps {
  id: string
  value: string
  onChange: (value: string) => void
  label?: string
}

export function DocumentTypeSelect({
  id,
  value,
  onChange,
  label = 'Document type',
}: DocumentTypeSelectProps) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-foreground">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-border px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
      >
        {DOCUMENT_TYPES.map((type) => (
          <option key={type.value} value={type.value}>
            {type.label}
          </option>
        ))}
      </select>
    </div>
  )
}
