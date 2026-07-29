import { PatientCard } from '@/components/patients/PatientCard'
import type { Patient } from '@/types/api'

interface PatientListProps {
  patients: Patient[]
  onArchiveRequest: (patient: Patient) => void
  showStatus?: boolean
  showUpdatedAt?: boolean
}

export function PatientList({
  patients,
  onArchiveRequest,
  showStatus,
  showUpdatedAt,
}: PatientListProps) {
  return (
    <ul className="flex flex-col gap-3">
      {patients.map((patient) => (
        <li key={patient.id}>
          <PatientCard
            patient={patient}
            onArchiveRequest={onArchiveRequest}
            showStatus={showStatus}
            showUpdatedAt={showUpdatedAt}
          />
        </li>
      ))}
    </ul>
  )
}
