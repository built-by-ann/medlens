import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { Button } from '@/components/common/Button'
import { FormError } from '@/components/common/FormError'
import {
  buildResolutionPayload,
  requiredFieldKeys,
  type DiscrepancyActionDescriptor,
} from '@/utils/discrepancyResolutionActions'
import type { DiscrepancyResolutionPayload } from '@/types/api'

export interface ResolveDiscrepancyTarget {
  discrepancyId: number
  medicationName: string
  action: DiscrepancyActionDescriptor
}

interface ResolveDiscrepancyDialogProps {
  target: ResolveDiscrepancyTarget | null
  isSubmitting: boolean
  error: string | null
  onCancel: () => void
  onConfirm: (payload: DiscrepancyResolutionPayload) => void
}

const HEADING_ID = 'resolve-discrepancy-heading'

// Built on the same native <dialog> pattern as DeleteAnalysisDialog/
// ArchivePatientDialog/StartAnalysisDialog: focus trapping, Escape-to-dismiss,
// and initial focus on Cancel all come from the platform rather than being
// reimplemented here. Handles every resolution action through one
// component - which fields (if any) are editable, and what the dialog says
// it's about to do, come entirely from the `action` descriptor
// (getDiscrepancyActions, discrepancyResolutionActions.ts) rather than a
// separate dialog per action type.
export function ResolveDiscrepancyDialog({
  target,
  isSubmitting,
  error,
  onCancel,
  onConfirm,
}: ResolveDiscrepancyDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({})
  const [note, setNote] = useState('')

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return

    if (target && !dialog.open) {
      dialog.showModal()
      setFieldValues(
        Object.fromEntries(target.action.fields.map((field) => [field.key, field.value])),
      )
      setNote('')
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

  function handleFieldChange(key: string, value: string) {
    setFieldValues((current) => ({ ...current, [key]: value }))
  }

  function handleSubmit() {
    if (!target || missingRequiredFields) return
    onConfirm(buildResolutionPayload(target.action, fieldValues, note))
  }

  const missingRequiredFields = target
    ? requiredFieldKeys(target.action).some((key) => !(fieldValues[key] ?? '').trim())
    : false

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={HEADING_ID}
      onClose={onCancel}
      onClick={handleBackdropClick}
      className="fixed inset-0 m-auto h-fit max-h-[85vh] w-[calc(100%-2rem)] max-w-md overflow-y-auto rounded-lg border border-border bg-surface p-6 text-foreground shadow-lg backdrop:bg-black/40"
    >
      {target && (
        <div className="flex flex-col gap-4">
          <div>
            <h2 id={HEADING_ID} className="text-lg font-semibold text-foreground">
              {target.action.label}: {target.medicationName}
            </h2>
            <p className="mt-1 text-sm text-muted">{target.action.description}</p>
          </div>

          {target.action.editable && target.action.fields.length > 0 && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {target.action.fields.map((field) => (
                <div key={field.key} className="flex flex-col gap-1">
                  <label
                    htmlFor={`resolve-field-${field.key}`}
                    className="text-sm font-medium text-foreground"
                  >
                    {field.label}
                    {requiredFieldKeys(target.action).includes(field.key) && (
                      <span aria-hidden="true"> *</span>
                    )}
                  </label>
                  <input
                    id={`resolve-field-${field.key}`}
                    value={fieldValues[field.key] ?? ''}
                    onChange={(event) => handleFieldChange(field.key, event.target.value)}
                    disabled={isSubmitting}
                    className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
                  />
                </div>
              ))}
            </div>
          )}

          <div className="flex flex-col gap-1">
            <label htmlFor="resolve-note" className="text-sm font-medium text-foreground">
              Note (optional)
            </label>
            <textarea
              id="resolve-note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              disabled={isSubmitting}
              rows={2}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
            />
          </div>

          {error && <FormError message={error} />}

          <div className="flex flex-wrap justify-end gap-2">
            <button
              ref={cancelButtonRef}
              type="button"
              onClick={onCancel}
              disabled={isSubmitting}
              className="cursor-pointer rounded-md px-4 py-2 text-sm font-medium text-muted hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cancel
            </button>
            <Button
              type="button"
              onClick={handleSubmit}
              disabled={isSubmitting || missingRequiredFields}
            >
              {isSubmitting ? 'Saving...' : 'Confirm'}
            </Button>
          </div>
        </div>
      )}
    </dialog>
  )
}
