import { Link } from 'react-router-dom'
import { Card } from '@/components/common/Card'
import { patientDetailPath, patientEditPath } from '@/routes/paths'
import type { Patient } from '@/types/api'

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

interface PatientCardProps {
  patient: Patient
  onArchiveRequest: (patient: Patient) => void
}

export function PatientCard({ patient, onArchiveRequest }: PatientCardProps) {
  const fullName = `${patient.first_name} ${patient.last_name}`

  return (
    <Card className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 flex-col gap-1">
        <Link
          to={patientDetailPath(patient.id)}
          className="truncate text-sm font-semibold text-slate-900 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          {fullName}
        </Link>
        <p className="flex flex-wrap gap-x-3 text-xs text-slate-500">
          <span>DOB: {formatDate(patient.date_of_birth)}</span>
          {patient.external_mrn && <span>MRN: {patient.external_mrn}</span>}
        </p>
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        <Link
          to={patientDetailPath(patient.id)}
          className="rounded-md px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          View
        </Link>
        <Link
          to={patientEditPath(patient.id)}
          className="rounded-md px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Edit
        </Link>
        <button
          type="button"
          onClick={() => onArchiveRequest(patient)}
          aria-label={`Archive ${fullName}`}
          className="rounded-md px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Archive
        </button>
      </div>
    </Card>
  )
}
