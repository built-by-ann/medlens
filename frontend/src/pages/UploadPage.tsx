import { PageHeader } from '@/components/common/PageHeader'
import { Card } from '@/components/common/Card'

export function UploadPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Upload documents" description="Add clinical documents for analysis." />
      <Card>
        <p className="text-sm text-slate-600">Document upload will be added in a future issue.</p>
      </Card>
    </div>
  )
}
