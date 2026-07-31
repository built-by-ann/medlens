import { useEffect, useRef, type MouseEvent } from 'react'
import { Button } from '@/components/common/Button'
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
      className="fixed inset-0 m-auto h-fit w-[calc(100%-2rem)] max-w-sm rounded-lg border border-slate-200 p-6 shadow-lg backdrop:bg-slate-900/40"
    >
      {patient && (
        <div className="flex flex-col gap-4">
          <h2 id="archive-patient-heading" className="text-lg font-semibold text-slate-900">
            Archive {patient.first_name} {patient.last_name}?
          </h2>
          <p className="text-sm text-slate-600">
            This removes {patient.first_name} {patient.last_name} from your active patient list.
            Their record is kept, and you can still open it directly whenever you need to.
          </p>
          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}
          <div className="flex flex-wrap justify-end gap-2">
            <button
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
              {isSubmitting ? 'Archiving...' : 'Archive patient'}
            </Button>
          </div>
        </div>
      )}
    </dialog>
  )
}
