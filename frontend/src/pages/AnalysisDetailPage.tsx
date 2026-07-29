import { Link, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { Card } from '@/components/common/Card'
import { patientAnalysesPath } from '@/routes/paths'

export function AnalysisDetailPage() {
  const { patientId, analysisId } = useParams<{ patientId: string; analysisId: string }>()

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={`Analysis #${analysisId}`}
        description="Medication summary and discrepancies."
      />

      {patientId && (
        <Link
          to={patientAnalysesPath(patientId)}
          className="self-start text-sm text-slate-600 hover:underline"
        >
          ← Back to analyses
        </Link>
      )}

      <Card>
        <p className="text-sm text-slate-600">
          Analysis detail content will be added in a future issue.
        </p>
      </Card>
    </div>
  )
}
