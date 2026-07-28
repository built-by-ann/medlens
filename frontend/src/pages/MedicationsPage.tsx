import { PageHeader } from '@/components/common/PageHeader'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { MedicationForm } from '@/components/medications/MedicationForm'
import { MedicationList } from '@/components/medications/MedicationList'
import { EmptyMedicationState } from '@/components/medications/EmptyMedicationState'
import { useMedications } from '@/hooks/useMedications'

export function MedicationsPage() {
  const { medications, isLoading, error, retry, addMedication, editMedication, removeMedication } =
    useMedications()

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Your medications"
        description="Keep your own medication list up to date. MedLens compares it against what your clinical documents say to find discrepancies."
      />

      <section aria-labelledby="medication-list-heading" className="flex flex-col gap-4">
        <h2 id="medication-list-heading" className="text-lg font-semibold text-slate-900">
          Current medications
        </h2>

        {isLoading && <LoadingSpinner label="Loading your medications" />}

        {!isLoading && error && (
          <ErrorState title="Couldn't load your medications" message={error} onRetry={retry} />
        )}

        {!isLoading && !error && medications.length === 0 && <EmptyMedicationState />}

        {!isLoading && !error && medications.length > 0 && (
          <MedicationList
            medications={medications}
            onEdit={editMedication}
            onDelete={removeMedication}
          />
        )}
      </section>

      <MedicationForm onAdd={addMedication} />
    </div>
  )
}
