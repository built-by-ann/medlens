import { useEffect, useRef, type MouseEvent } from 'react'
import { Button } from '@/components/common/Button'
import { FormError } from '@/components/common/FormError'
import type { Patient } from '@/types/api'

interface ArchivePatientDialogProps {
  patient: Patient | null
  isSubmitting: boolean
  error: string | null
  onCancel: () => void
  onConfirm: () => void
}

/**
 * The app's first dialog. Built on the native <dialog> element via
 * showModal()/close() rather than a hand-rolled overlay, since that gets
 * focus trapping, Escape-to-dismiss, and focus restoration on close for
 * free. `onClose` fires for every close path (Escape, our own close() call
 * below, a future method="dialog" submit), so it's the single place that
 * syncs React state back to "closed" - the DOM and React state can't end
 * up disagreeing.
 */
export function ArchivePatientDialog({
  patient,
  isSubmitting,
  error,
  onCancel,
  onConfirm,
}: ArchivePatientDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return

    if (patient && !dialog.open) {
      dialog.showModal()
    } else if (!patient && dialog.open) {
      dialog.close()
    }
  }, [patient])

  function handleBackdropClick(event: MouseEvent<HTMLDialogElement>) {
    if (event.target === dialogRef.current) {
      onCancel()
    }
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="archive-patient-heading"
      onClose={onCancel}
      onClick={handleBackdropClick}
      className="fixed inset-0 m-auto h-fit w-[calc(100%-2rem)] max-w-sm rounded-lg border border-border bg-surface p-6 text-foreground shadow-lg backdrop:bg-black/40"
    >
      {patient && (
        <div className="flex flex-col gap-4">
          <h2 id="archive-patient-heading" className="text-lg font-semibold text-foreground">
            Archive {patient.first_name} {patient.last_name}?
          </h2>
          <p className="text-sm text-muted">
            This removes {patient.first_name} {patient.last_name} from your active patient list.
            Their record is kept, and you can still open it directly whenever you need to.
          </p>
          {error && <FormError message={error} />}
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={onCancel}
              disabled={isSubmitting}
              className="rounded-md px-4 py-2 text-sm font-medium text-muted hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cancel
            </button>
            <Button
              type="button"
              onClick={onConfirm}
              disabled={isSubmitting}
              className="bg-danger text-danger-foreground hover:bg-danger/90"
            >
              {isSubmitting ? 'Archiving...' : 'Archive patient'}
            </Button>
          </div>
        </div>
      )}
    </dialog>
  )
}
