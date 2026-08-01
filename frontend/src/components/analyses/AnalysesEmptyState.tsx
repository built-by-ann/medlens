import { Link } from 'react-router-dom'
import { Card } from '@/components/common/Card'
import { createAnalysisPath } from '@/routes/paths'

interface AnalysesEmptyStateProps {
  patientId: number
}

export function AnalysesEmptyState({ patientId }: AnalysesEmptyStateProps) {
  return (
    <Card className="flex flex-col items-center gap-4 py-12 text-center">
      <h3 className="text-lg font-semibold text-foreground">No analyses yet</h3>
      <p className="max-w-md text-sm text-muted">
        MedLens compares medication information across this patient's clinical documents and flags
        potential inconsistencies for review. Upload their first set of documents to generate the
        first analysis.
      </p>
      <Link
        to={createAnalysisPath(patientId)}
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
      >
        Start an analysis
      </Link>
    </Card>
  )
}
