import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { PatientSearch } from '@/components/patients/PatientSearch'
import { filterPatients } from '@/components/patients/filterPatients'
import type { Patient } from '@/types/api'

interface StartAnalysisDialogProps {
  isOpen: boolean
  patients: Patient[]
  onClose: () => void
  onSelectPatient: (patient: Patient) => void
}

/**
 * The Dashboard's "New Analysis" quick action prompts for a patient before
 * it can go anywhere (Issue #157); this is that prompt. Built on the same
 * native <dialog> pattern as ArchivePatientDialog/DeleteAnalysisDialog, but
 * unlike those, there's no single "target" object that can double as the
 * open/closed flag here (the content is a searchable list, not one confirm
 * message), so `isOpen` is explicit. Selecting a patient (a single click,
 * no separate confirm step) is itself the confirmation; the caller is
 * expected to navigate straight into CreateAnalysisPage for that patient.
 */
export function StartAnalysisDialog({
  isOpen,
  patients,
  onClose,
  onSelectPatient,
}: StartAnalysisDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [searchTerm, setSearchTerm] = useState('')

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return

    if (isOpen && !dialog.open) {
      dialog.showModal()
      // Start from a clean search every time the dialog opens, rather than
      // whatever was typed the last time it was open.
      setSearchTerm('')
    } else if (!isOpen && dialog.open) {
      dialog.close()
    }
  }, [isOpen])

  function handleBackdropClick(event: MouseEvent<HTMLDialogElement>) {
    if (event.target === dialogRef.current) {
      onClose()
    }
  }

  const filteredPatients = filterPatients(patients, searchTerm)

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="start-analysis-heading"
      onClose={onClose}
      onClick={handleBackdropClick}
      className="fixed inset-0 m-auto h-fit max-h-[80vh] w-[calc(100%-2rem)] max-w-md overflow-y-auto rounded-lg border border-border bg-surface p-6 text-foreground shadow-lg backdrop:bg-black/40"
    >
      {isOpen && (
        <div className="flex flex-col gap-4">
          <div>
            <h2 id="start-analysis-heading" className="text-lg font-semibold text-foreground">
              Start an analysis
            </h2>
            <p className="mt-1 text-sm text-muted">Choose a patient to build it for.</p>
          </div>

          <PatientSearch value={searchTerm} onChange={setSearchTerm} />

          {filteredPatients.length === 0 ? (
            <p className="text-sm text-muted">No patients match your search.</p>
          ) : (
            <ul className="flex max-h-64 flex-col gap-2 overflow-y-auto">
              {filteredPatients.map((patient) => (
                <li key={patient.id}>
                  <button
                    type="button"
                    onClick={() => onSelectPatient(patient)}
                    className="w-full rounded-md border border-border px-3 py-2 text-left text-sm hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
                  >
                    <span className="font-medium text-foreground">
                      {patient.first_name} {patient.last_name}
                    </span>
                    {patient.external_mrn && (
                      <span className="ml-2 text-xs text-muted">MRN: {patient.external_mrn}</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="flex justify-end">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-4 py-2 text-sm font-medium text-muted hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </dialog>
  )
}
