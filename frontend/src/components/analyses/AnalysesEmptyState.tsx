import { Link } from 'react-router-dom'
import { Card } from '@/components/common/Card'
import { patientUploadPath } from '@/routes/paths'

interface AnalysesEmptyStateProps {
  patientId: number
}

export function AnalysesEmptyState({ patientId }: AnalysesEmptyStateProps) {
  return (
    <Card className="flex flex-col items-center gap-4 py-12 text-center">
      <h3 className="text-lg font-semibold text-slate-900">No analyses yet</h3>
      <p className="max-w-md text-sm text-slate-600">
        MedLens compares medication information across this patient's clinical documents and flags
        potential inconsistencies for review. Upload their first set of documents to generate the
        first analysis.
      </p>
      <Link
        to={patientUploadPath(patientId)}
        className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      >
        Start an analysis
      </Link>
    </Card>
  )
}
