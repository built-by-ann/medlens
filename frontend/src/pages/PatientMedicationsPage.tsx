import { Link, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { MedicationForm } from '@/components/medications/MedicationForm'
import { MedicationList } from '@/components/medications/MedicationList'
import { EmptyMedicationState } from '@/components/medications/EmptyMedicationState'
import { usePatient } from '@/hooks/usePatient'
import { usePatientMedications } from '@/hooks/usePatientMedications'
import { patientDetailPath } from '@/routes/paths'

export function PatientMedicationsPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)

  const {
    patient,
    isLoading: isPatientLoading,
    error: patientError,
    retry: retryPatient,
  } = usePatient(id)
  const {
    medications,
    isLoading: areMedicationsLoading,
    error: medicationsError,
    retry: retryMedications,
    addMedication,
    editMedication,
    removeMedication,
  } = usePatientMedications(id)

  return (
    <div className="flex flex-col gap-8">
      {isPatientLoading && <LoadingSpinner label="Loading patient" />}

      {!isPatientLoading && patientError && (
        <ErrorState
          title="Couldn't load this patient"
          message={patientError}
          onRetry={retryPatient}
        />
      )}

      {!isPatientLoading && !patientError && patient && (
        <>
          <PageHeader
            title={`Medications for ${patient.first_name} ${patient.last_name}`}
            description="Keep this patient's medication list up to date. MedLens compares it against their clinical documents to find discrepancies."
          />

          <Link
            to={patientDetailPath(patient.id)}
            className="self-start text-sm text-slate-600 hover:underline"
          >
            ← Back to {patient.first_name} {patient.last_name}
          </Link>

          <section aria-labelledby="medication-list-heading" className="flex flex-col gap-4">
            <h2 id="medication-list-heading" className="text-lg font-semibold text-slate-900">
              Current medications
            </h2>

            {areMedicationsLoading && <LoadingSpinner label="Loading medications" />}

            {!areMedicationsLoading && medicationsError && (
              <ErrorState
                title="Couldn't load medications"
                message={medicationsError}
                onRetry={retryMedications}
              />
            )}

            {!areMedicationsLoading && !medicationsError && medications.length === 0 && (
              <EmptyMedicationState />
            )}

            {!areMedicationsLoading && !medicationsError && medications.length > 0 && (
              <MedicationList
                medications={medications}
                onEdit={editMedication}
                onDelete={removeMedication}
              />
            )}
          </section>

          <MedicationForm onAdd={addMedication} />
        </>
      )}
    </div>
  )
}
