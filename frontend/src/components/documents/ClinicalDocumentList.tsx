import { ClinicalDocumentCard } from '@/components/documents/ClinicalDocumentCard'
import type { ClinicalDocument } from '@/types/api'

interface ClinicalDocumentListProps {
  documents: ClinicalDocument[]
  onDelete: (id: number) => Promise<void>
}

export function ClinicalDocumentList({ documents, onDelete }: ClinicalDocumentListProps) {
  return (
    <ul className="flex flex-col gap-4">
      {documents.map((document) => (
        <li key={document.id}>
          <ClinicalDocumentCard document={document} onDelete={onDelete} />
        </li>
      ))}
    </ul>
  )
}
