import { Card } from '@/components/common/Card'
import { SummaryStat } from '@/components/common/SummaryStat'
import { patientStatusLabel } from '@/utils/patientStatus'
import type { Patient } from '@/types/api'

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

function formatDateTime(value: string | null): string | null {
  if (!value) {
    return null
  }

  return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

interface PatientDetailsProps {
  patient: Patient
}

export function PatientDetails({ patient }: PatientDetailsProps) {
  const createdAt = formatDateTime(patient.created_at)
  const updatedAt = formatDateTime(patient.updated_at)

  return (
    <Card className="flex flex-col gap-4">
      <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <SummaryStat label="Date of birth" value={formatDate(patient.date_of_birth)} />
        <SummaryStat label="Status" value={patientStatusLabel(patient.status)} />
        {patient.external_mrn && <SummaryStat label="External MRN" value={patient.external_mrn} />}
        {createdAt && <SummaryStat label="Added" value={createdAt} />}
        {updatedAt && <SummaryStat label="Last updated" value={updatedAt} />}
      </dl>
      {patient.notes && (
        <div className="flex flex-col gap-1 border-t border-border pt-4">
          <span className="text-xs font-medium tracking-wide text-muted uppercase">Notes</span>
          <p className="text-sm text-foreground">{patient.notes}</p>
        </div>
      )}
    </Card>
  )
}
