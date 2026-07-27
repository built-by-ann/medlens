import { LoadingSpinner } from '@/components/common/LoadingSpinner'

export function LoadingPage() {
  return (
    <div className="flex justify-center py-16">
      <LoadingSpinner label="Loading page" />
    </div>
  )
}
