import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <h1 className="text-2xl font-semibold text-foreground">Page not found</h1>
      <p className="text-sm text-muted">
        The page you're looking for doesn't exist or may have been moved.
      </p>
      <Link
        to="/dashboard"
        className="rounded-md px-3 py-2 text-sm font-medium text-link hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
      >
        Return to dashboard
      </Link>
    </div>
  )
}
