import { Link } from 'react-router-dom'
import { ROUTES } from '@/routes/paths'

export function HomePage() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-12 sm:px-6">
      <h1 className="text-2xl font-semibold text-foreground">MedLens</h1>
      <p className="text-sm text-muted">AI-powered clinical documentation reconciliation.</p>
      <div className="flex gap-3">
        <Link
          to={ROUTES.login}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-hover"
        >
          Log in
        </Link>
        <Link
          to={ROUTES.signup}
          className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-hover"
        >
          Sign up
        </Link>
      </div>
    </div>
  )
}
