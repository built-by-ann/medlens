import { Button } from '@/components/common/Button'
import { Card } from '@/components/common/Card'

interface ErrorStateProps {
  title: string
  message: string
  onRetry: () => void
}

export function ErrorState({ title, message, onRetry }: ErrorStateProps) {
  return (
    <Card role="alert" className="flex flex-col items-center gap-4 py-12 text-center">
      <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
      <p className="max-w-md text-sm text-slate-600">{message}</p>
      <Button onClick={onRetry}>Try again</Button>
    </Card>
  )
}
