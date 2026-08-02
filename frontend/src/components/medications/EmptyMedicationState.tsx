import { Card } from '@/components/common/Card'

interface EmptyMedicationStateProps {
  message?: string
  /**
   * Where the "Add your first medication" action goes. A route (e.g.
   * `patientMedicationsPath(patientId)`) on pages where the add form lives
   * elsewhere, or an in-page anchor (e.g. `#add-medication-heading`) on
   * `PatientMedicationsPage` itself, where it already lives directly below -
   * see that page for the matching `id`.
   */
  addMedicationHref: string
}

export function EmptyMedicationState({
  message = "Add your first medication to start this patient's medication list.",
  addMedicationHref,
}: EmptyMedicationStateProps) {
  return (
    <Card className="flex flex-col items-center gap-4 py-12 text-center">
      <h3 className="text-lg font-semibold text-foreground">No medications added yet</h3>
      <p className="max-w-md text-sm text-muted">{message}</p>
      <a
        href={addMedicationHref}
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
      >
        Add your first medication
      </a>
    </Card>
  )
}
