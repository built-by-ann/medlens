interface ErrorPageProps {
  message?: string
}

export function ErrorPage({ message }: ErrorPageProps) {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <h1 className="text-2xl font-semibold text-foreground">Something went wrong</h1>
      <p className="text-sm text-muted">
        {message ?? 'An unexpected error occurred. Please try again.'}
      </p>
    </div>
  )
}
