import { useParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { Card } from '@/components/common/Card'

export function AnalysisDetailPage() {
  const { id } = useParams<{ id: string }>()

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={`Analysis #${id}`} description="Medication summary and discrepancies." />
      <Card>
        <p className="text-sm text-slate-600">
          Analysis detail content will be added in a future issue.
        </p>
      </Card>
    </div>
  )
}
