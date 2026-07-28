import { Link } from 'react-router-dom'
import { Card } from '@/components/common/Card'
import { ROUTES } from '@/routes/paths'

export function DashboardEmptyState() {
  return (
    <Card className="flex flex-col items-center gap-4 py-12 text-center">
      <h3 className="text-lg font-semibold text-slate-900">No analyses yet</h3>
      <p className="max-w-md text-sm text-slate-600">
        MedLens compares medication information across your clinical documents and flags potential
        inconsistencies for review. Upload your first set of documents to generate your first
        analysis.
      </p>
      <Link
        to={ROUTES.upload}
        className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      >
        Start your first analysis
      </Link>
    </Card>
  )
}
