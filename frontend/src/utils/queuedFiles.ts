import { effectiveFileTitle } from '@/api/clinicalDocuments'
import type { QueuedFile } from '@/hooks/useCreateAnalysis'

// Same-name-and-size is a good enough proxy for "the same file" without
// reading file contents; shared by every page that lets a provider queue
// files before they become real ClinicalDocuments.
export function isDuplicateFile(existing: QueuedFile[], candidate: File): boolean {
  return existing.some(
    (queued) => queued.file.name === candidate.name && queued.file.size === candidate.size,
  )
}

// Matches a queued file against a patient's already-saved documents by the
// exact title it would be given on upload (effectiveFileTitle, the
// provider's own edited title if they've set one, otherwise the same
// filename-derived default uploadClinicalDocumentFile itself falls back
// to), case-insensitively. This is a same-name warning, not real content
// comparison: nothing here reads file contents, so it can both under- and
// over-match (a renamed duplicate slips through; two unrelated notes that
// happen to share a title get flagged); a deliberate, cheap tradeoff over
// hashing file contents for what is only ever a non-blocking heads-up.
export function findDuplicateExistingTitle(
  queued: Pick<QueuedFile, 'file' | 'title'>,
  existingTitles: string[],
): string | undefined {
  const candidateTitle = effectiveFileTitle(queued.file.name, queued.title).trim().toLowerCase()

  return existingTitles.find((title) => title.trim().toLowerCase() === candidateTitle)
}
