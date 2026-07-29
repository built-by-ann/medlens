import { RecentDocumentCard } from '@/components/documents/RecentDocumentCard'
import type { ClinicalDocument } from '@/types/api'

interface RecentDocumentsListProps {
  documents: ClinicalDocument[]
}

export function RecentDocumentsList({ documents }: RecentDocumentsListProps) {
  return (
    <ul className="flex flex-col gap-3">
      {documents.map((document) => (
        <li key={document.id}>
          <RecentDocumentCard document={document} />
        </li>
      ))}
    </ul>
  )
}
