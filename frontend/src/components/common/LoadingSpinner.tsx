interface LoadingSpinnerProps {
  label?: string
}

export function LoadingSpinner({ label = 'Loading' }: LoadingSpinnerProps) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-8 text-muted">
      <span
        aria-hidden="true"
        className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-primary"
      />
      <span className="text-sm">{label}</span>
    </div>
  )
}
