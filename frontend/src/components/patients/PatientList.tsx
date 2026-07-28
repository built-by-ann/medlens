import { PatientCard } from '@/components/patients/PatientCard'
import type { Patient } from '@/types/api'

interface PatientListProps {
  patients: Patient[]
  onArchiveRequest: (patient: Patient) => void
}

export function PatientList({ patients, onArchiveRequest }: PatientListProps) {
  return (
    <ul className="flex flex-col gap-3">
      {patients.map((patient) => (
        <li key={patient.id}>
          <PatientCard patient={patient} onArchiveRequest={onArchiveRequest} />
        </li>
      ))}
    </ul>
  )
}
