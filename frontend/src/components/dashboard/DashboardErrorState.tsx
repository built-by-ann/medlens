import { Button } from '@/components/common/Button'
import { Card } from '@/components/common/Card'

interface DashboardErrorStateProps {
  message: string
  onRetry: () => void
}

export function DashboardErrorState({ message, onRetry }: DashboardErrorStateProps) {
  return (
    <Card role="alert" className="flex flex-col items-center gap-4 py-12 text-center">
      <h3 className="text-lg font-semibold text-slate-900">Couldn&apos;t load your analyses</h3>
      <p className="max-w-md text-sm text-slate-600">{message}</p>
      <Button onClick={onRetry}>Try again</Button>
    </Card>
  )
}
