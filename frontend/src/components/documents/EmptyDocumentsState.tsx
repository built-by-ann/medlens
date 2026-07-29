import { Link } from 'react-router-dom'
import { Card } from '@/components/common/Card'
import { patientUploadPath } from '@/routes/paths'

interface EmptyDocumentsStateProps {
  patientId: number
}

export function EmptyDocumentsState({ patientId }: EmptyDocumentsStateProps) {
  return (
    <Card className="flex flex-col items-center gap-4 py-12 text-center">
      <h3 className="text-lg font-semibold text-slate-900">No documents uploaded</h3>
      <p className="max-w-md text-sm text-slate-600">
        Upload a visit note, discharge summary, or medication list to start building this patient's
        clinical record.
      </p>
      <Link
        to={patientUploadPath(patientId)}
        className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      >
        Upload your first document
      </Link>
    </Card>
  )
}
