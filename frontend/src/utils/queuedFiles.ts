import type { QueuedFile } from '@/hooks/useCreateAnalysis'

// Same-name-and-size is a good enough proxy for "the same file" without
// reading file contents - shared by every page that lets a provider queue
// files before they become real ClinicalDocuments.
export function isDuplicateFile(existing: QueuedFile[], candidate: File): boolean {
  return existing.some(
    (queued) => queued.file.name === candidate.name && queued.file.size === candidate.size,
  )
}
