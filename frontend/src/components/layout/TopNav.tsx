import { NavLink } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/utils/cn'
import { ROUTES } from '@/routes/paths'

const navLinkClassName = ({ isActive }: { isActive: boolean }) =>
  cn(
    'rounded-md px-3 py-2 text-sm font-medium',
    'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600',
    isActive ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100',
  )

export function TopNav() {
  const { user, logout } = useAuth()

  return (
    <header className="border-b border-slate-200 bg-white">
      <nav
        aria-label="Main navigation"
        className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3 sm:px-6"
      >
        <span className="text-base font-semibold text-slate-900">MedLens</span>

        <ul className="flex items-center gap-1">
          <li>
            <NavLink to={ROUTES.dashboard} className={navLinkClassName}>
              Dashboard
            </NavLink>
          </li>
          <li>
            <NavLink to={ROUTES.upload} className={navLinkClassName}>
              Upload
            </NavLink>
          </li>
          <li>
            <NavLink to={ROUTES.medications} className={navLinkClassName}>
              Medications
            </NavLink>
          </li>
        </ul>

        <div>
          {user ? (
            <button
              type="button"
              onClick={logout}
              className="rounded-md px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            >
              Log out
            </button>
          ) : (
            <NavLink to={ROUTES.login} className={navLinkClassName}>
              Log in
            </NavLink>
          )}
        </div>
      </nav>
    </header>
  )
}
