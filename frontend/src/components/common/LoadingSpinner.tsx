interface LoadingSpinnerProps {
  label?: string
}

export function LoadingSpinner({ label = 'Loading' }: LoadingSpinnerProps) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-8 text-slate-500">
      <span
        aria-hidden="true"
        className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-blue-600"
      />
      <span className="text-sm">{label}</span>
    </div>
  )
}
