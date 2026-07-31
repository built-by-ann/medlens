import { useEffect, useRef, type MouseEvent } from 'react'
import { Button } from '@/components/common/Button'
import { FormError } from '@/components/common/FormError'

interface DeleteAnalysisTarget {
  id: number
  patientName: string
}

interface DeleteAnalysisDialogProps {
  target: DeleteAnalysisTarget | null
  isSubmitting: boolean
  error: string | null
  onCancel: () => void
  onConfirm: () => void
}

// Built on the native <dialog> element via showModal()/close(), the same
// pattern ArchivePatientDialog established: focus trapping, Escape-to-dismiss,
// and initial focus on the first focusable control (Cancel, since it's
// listed before the destructive action below) all come for free.
export function DeleteAnalysisDialog({
  target,
  isSubmitting,
  error,
  onCancel,
  onConfirm,
}: DeleteAnalysisDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return

    if (target && !dialog.open) {
      dialog.showModal()
      // Explicit rather than relying on the browser's own "focus the first
      // focusable element" default: that default isn't consistent across
      // environments, and the safest action (Cancel) is what this dialog
      // should always land focus on, not whatever happens to be first in
      // markup.
      cancelButtonRef.current?.focus()
    } else if (!target && dialog.open) {
      dialog.close()
    }
  }, [target])

  function handleBackdropClick(event: MouseEvent<HTMLDialogElement>) {
    if (event.target === dialogRef.current) {
      onCancel()
    }
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="delete-analysis-heading"
      onClose={onCancel}
      onClick={handleBackdropClick}
      className="fixed inset-0 m-auto h-fit w-[calc(100%-2rem)] max-w-sm rounded-lg border border-slate-200 p-6 shadow-lg backdrop:bg-slate-900/40"
    >
      {target && (
        <div className="flex flex-col gap-4">
          <h2 id="delete-analysis-heading" className="text-lg font-semibold text-slate-900">
            Delete this analysis?
          </h2>
          <p className="text-sm text-slate-600">
            Analysis #{target.id} for {target.patientName}
          </p>
          <p className="text-sm text-slate-600">
            This action permanently removes the analysis and its associated reconciliation findings.
            This cannot be undone.
          </p>
          {error && <FormError message={error} />}
          <div className="flex flex-wrap justify-end gap-2">
            <button
              ref={cancelButtonRef}
              type="button"
              onClick={onCancel}
              disabled={isSubmitting}
              className="rounded-md px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cancel
            </button>
            <Button
              type="button"
              onClick={onConfirm}
              disabled={isSubmitting}
              className="bg-red-600 hover:bg-red-700"
            >
              {isSubmitting ? 'Deleting...' : 'Delete analysis'}
            </Button>
          </div>
        </div>
      )}
    </dialog>
  )
}
