import { MedicationCard } from '@/components/medications/MedicationCard'
import type { MedicationPayload } from '@/api/medications'
import type { Medication } from '@/types/api'

interface MedicationListProps {
  medications: Medication[]
  onEdit: (id: number, payload: MedicationPayload) => Promise<Medication>
  onDelete: (id: number) => Promise<void>
}

export function MedicationList({ medications, onEdit, onDelete }: MedicationListProps) {
  return (
    <ul className="flex flex-col gap-4">
      {medications.map((medication) => (
        <li key={medication.id}>
          <MedicationCard medication={medication} onEdit={onEdit} onDelete={onDelete} />
        </li>
      ))}
    </ul>
  )
}
