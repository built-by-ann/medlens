import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ROUTES } from '@/routes/paths'

interface PublicOnlyRouteProps {
  children: ReactNode
}

/**
 * The inverse of ProtectedRoute: keeps an already-authenticated user off
 * Login/Signup by sending them to the dashboard instead. Not used for every
 * public page (Home stays reachable regardless of auth state), only the
 * ones an authenticated visitor has no reason to see.
 */
export function PublicOnlyRoute({ children }: PublicOnlyRouteProps) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <LoadingSpinner />
  }

  if (isAuthenticated) {
    return <Navigate to={ROUTES.dashboard} replace />
  }

  return <>{children}</>
}
