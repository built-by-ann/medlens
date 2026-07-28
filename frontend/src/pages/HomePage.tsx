import { Link } from 'react-router-dom'
import { ROUTES } from '@/routes/paths'

export function HomePage() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-12 sm:px-6">
      <h1 className="text-2xl font-semibold text-slate-900">MedLens</h1>
      <p className="text-sm text-slate-600">AI-powered clinical documentation reconciliation.</p>
      <div className="flex gap-3">
        <Link
          to={ROUTES.login}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Log in
        </Link>
        <Link
          to={ROUTES.signup}
          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
        >
          Sign up
        </Link>
      </div>
    </div>
  )
}
