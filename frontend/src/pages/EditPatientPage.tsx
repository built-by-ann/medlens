import { Link, useNavigate, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { PatientForm } from '@/components/patients/PatientForm'
import { PatientPageNav } from '@/components/patients/PatientPageNav'
import { usePatient } from '@/hooks/usePatient'
import { updatePatient, type PatientPayload } from '@/api/patients'
import { patientDetailPath } from '@/routes/paths'
import type { Patient } from '@/types/api'

function toPayload(patient: Patient): PatientPayload {
  return {
    firstName: patient.first_name,
    lastName: patient.last_name,
    dateOfBirth: patient.date_of_birth,
    externalMrn: patient.external_mrn ?? '',
    notes: patient.notes ?? '',
  }
}

export function EditPatientPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const navigate = useNavigate()
  const id = Number(patientId)
  const { patient, isLoading, error, retry } = usePatient(id)

  async function handleSubmit(payload: PatientPayload) {
    await updatePatient(id, payload)
    navigate(patientDetailPath(id))
  }

  return (
    <div className="flex flex-col gap-6">
      {!isLoading && !error && patient && (
        <PatientPageNav
          patient={patient}
          trail={[{ label: 'Edit patient' }]}
          backTo={patientDetailPath(id)}
          backLabel={`${patient.first_name} ${patient.last_name}`}
        />
      )}

      <PageHeader title="Edit patient" description="Update this patient's information." />

      {isLoading && <LoadingSpinner label="Loading patient" />}

      {!isLoading && error && (
        <ErrorState title="Couldn't load this patient" message={error} onRetry={retry} />
      )}

      {!isLoading && !error && patient && (
        <>
          <PatientForm
            initialValues={toPayload(patient)}
            submitLabel="Save changes"
            onSubmit={handleSubmit}
          />
          <Link
            to={patientDetailPath(id)}
            replace
            className="self-start text-sm text-danger hover:underline"
          >
            Cancel
          </Link>
        </>
      )}
    </div>
  )
}
