import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ROUTES } from '@/routes/paths'

interface ProtectedRouteProps {
  children: ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  // While the initial session restore is in progress, isAuthenticated is
  // reliably false regardless of whether a valid session actually exists,
  // so redirecting on it here would flash to /login for every authenticated
  // user on page load. Showing a loading state instead avoids that flicker.
  if (isLoading) {
    return <LoadingSpinner />
  }

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.login} state={{ from: location }} replace />
  }

  return <>{children}</>
}
