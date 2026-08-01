import { Link } from 'react-router-dom'
import { Card } from '@/components/common/Card'
import { patientUploadPath } from '@/routes/paths'

interface EmptyDocumentsStateProps {
  patientId: number
}

export function EmptyDocumentsState({ patientId }: EmptyDocumentsStateProps) {
  return (
    <Card className="flex flex-col items-center gap-4 py-12 text-center">
      <h3 className="text-lg font-semibold text-foreground">No documents uploaded</h3>
      <p className="max-w-md text-sm text-muted">
        Upload a visit note, discharge summary, or medication list to start building this patient's
        clinical record.
      </p>
      <Link
        to={patientUploadPath(patientId)}
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
      >
        Upload your first document
      </Link>
    </Card>
  )
}
