import { NavLink } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/utils/cn'
import { ROUTES } from '@/routes/paths'

const navLinkClassName = ({ isActive }: { isActive: boolean }) =>
  cn(
    'rounded-md px-3 py-2 text-sm font-medium',
    'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
    isActive ? 'bg-primary text-primary-foreground' : 'text-header-foreground hover:bg-surface-hover',
  )

export function TopNav() {
  const { user, logout } = useAuth()

  return (
    <header className="border-b border-border bg-header">
      <nav
        aria-label="Main navigation"
        className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3 sm:px-6"
      >
        <span className="text-base font-semibold text-header-foreground">MedLens</span>

        <ul className="flex flex-wrap items-center gap-1">
          <li>
            <NavLink to={ROUTES.dashboard} className={navLinkClassName}>
              Dashboard
            </NavLink>
          </li>
          <li>
            <NavLink to={ROUTES.patients} className={navLinkClassName}>
              Patients
            </NavLink>
          </li>
          <li>
            <NavLink to={ROUTES.settings} className={navLinkClassName}>
              Settings
            </NavLink>
          </li>
        </ul>

        <div>
          {user ? (
            <button
              type="button"
              onClick={logout}
              className="rounded-md px-3 py-2 text-sm font-medium text-header-foreground hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
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
