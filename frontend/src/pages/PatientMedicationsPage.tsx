import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { Input } from '@/components/common/Input'
import { MedicationForm } from '@/components/medications/MedicationForm'
import { MedicationList } from '@/components/medications/MedicationList'
import { EmptyMedicationState } from '@/components/medications/EmptyMedicationState'
import { MedicationCsvUpload } from '@/components/medications/MedicationCsvUpload'
import { filterMedications } from '@/components/medications/filterMedications'
import { PatientPageNav } from '@/components/patients/PatientPageNav'
import { usePatient } from '@/hooks/usePatient'
import { usePatientMedications } from '@/hooks/usePatientMedications'
import { patientDetailPath } from '@/routes/paths'

export function PatientMedicationsPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)
  const [medicationsQuery, setMedicationsQuery] = useState('')

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
    importMedicationsCsv,
  } = usePatientMedications(id)

  const filteredMedications = filterMedications(medications, medicationsQuery)

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
          <PatientPageNav
            patient={patient}
            trail={[{ label: 'Medications' }]}
            backTo={patientDetailPath(patient.id)}
            backLabel={`${patient.first_name} ${patient.last_name}`}
          />

          <PageHeader
            title={`Medications for ${patient.first_name} ${patient.last_name}`}
            description="Keep this patient's medication list up to date. MedLens compares it against their clinical documents to find discrepancies."
          />

          <section aria-labelledby="medication-list-heading" className="flex flex-col gap-4">
            <h2 id="medication-list-heading" className="text-lg font-semibold text-foreground">
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
              <EmptyMedicationState
                message="Add a medication using the form below to start this patient's medication list."
                addMedicationHref="#add-medication-heading"
              />
            )}

            {!areMedicationsLoading && !medicationsError && medications.length > 0 && (
              <>
                <Input
                  type="search"
                  label="Search medications"
                  value={medicationsQuery}
                  onChange={(event) => setMedicationsQuery(event.target.value)}
                  placeholder="Search by name, dose, route, frequency, or status"
                  className="sm:max-w-xs"
                />

                {filteredMedications.length === 0 ? (
                  <p className="text-sm text-muted">No medications match your search.</p>
                ) : (
                  <MedicationList
                    medications={filteredMedications}
                    onEdit={editMedication}
                    onDelete={removeMedication}
                  />
                )}
              </>
            )}
          </section>

          <MedicationCsvUpload onImport={importMedicationsCsv} />

          <MedicationForm onAdd={addMedication} />
        </>
      )}
    </div>
  )
}
