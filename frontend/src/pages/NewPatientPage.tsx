import { Link, useNavigate } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { PatientForm } from '@/components/patients/PatientForm'
import { createPatient, type PatientPayload } from '@/api/patients'
import { ROUTES, patientDetailPath } from '@/routes/paths'

export function NewPatientPage() {
  const navigate = useNavigate()

  async function handleSubmit(payload: PatientPayload) {
    const created = await createPatient(payload)
    navigate(patientDetailPath(created.id))
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="New patient" description="Add a patient to start tracking their care." />
      <PatientForm submitLabel="Create patient" onSubmit={handleSubmit} />
      <Link to={ROUTES.patients} replace className="self-start text-sm text-danger hover:underline">
        Cancel
      </Link>
    </div>
  )
}
