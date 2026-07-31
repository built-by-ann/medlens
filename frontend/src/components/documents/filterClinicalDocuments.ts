import { documentTypeLabel } from '@/api/clinicalDocuments'
import type { ClinicalDocument } from '@/types/api'

/**
 * Client-side search over a patient's already-fetched documents (no backend
 * search parameter exists for this list, same reasoning as filterPatients.ts).
 * Matches title or document type label, case-insensitively. Returns a new
 * array and never mutates `documents`.
 */
export function filterClinicalDocuments(
  documents: ClinicalDocument[],
  searchTerm: string,
): ClinicalDocument[] {
  const normalized = searchTerm.trim().toLowerCase()

  if (!normalized) {
    return documents
  }

  return documents.filter((document) => {
    const title = document.title.toLowerCase()
    const typeLabel = documentTypeLabel(document.document_type).toLowerCase()

    return title.includes(normalized) || typeLabel.includes(normalized)
  })
}
