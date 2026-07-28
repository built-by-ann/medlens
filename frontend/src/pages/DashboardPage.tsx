import { PageHeader } from '@/components/common/PageHeader'
import { Card } from '@/components/common/Card'

export function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Dashboard"
        description="An overview of your clinical documents and analyses."
      />
      <Card>
        <p className="text-sm text-slate-600">Dashboard content will be added in a future issue.</p>
      </Card>
    </div>
  )
}
