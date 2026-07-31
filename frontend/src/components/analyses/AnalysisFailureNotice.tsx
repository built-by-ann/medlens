import { cn } from '@/utils/cn'

interface AnalysisFailureNoticeProps {
  message: string
  className?: string
}

/**
 * The message a completed-but-failed Analysis carries (`error_message`) -
 * shared so every place an analysis's own failure is shown (AnalysisDetailPage,
 * RecentAnalysisCard) uses the same wording and is announced to assistive
 * tech the same way. Previously each place duplicated this as a plain
 * paragraph with no shared label, and one of the two had no `role` at all.
 * Distinct from FormError: this isn't a failed *action* (submitting a form,
 * deleting something) - it's a fact about a persisted record, so it always
 * carries its own "Analysis failed" label rather than relying on context.
 */
export function AnalysisFailureNotice({ message, className }: AnalysisFailureNoticeProps) {
  return (
    <p role="alert" className={cn('text-sm break-words text-red-600', className)}>
      <span className="font-medium">Analysis failed: </span>
      {message}
    </p>
  )
}
