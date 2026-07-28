import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { RecentAnalysesList } from '@/components/dashboard/RecentAnalysesList'
import { DashboardEmptyState } from '@/components/dashboard/DashboardEmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { useRecentAnalyses } from '@/hooks/useRecentAnalyses'
import { useAuth } from '@/hooks/useAuth'
import { ROUTES } from '@/routes/paths'

export function DashboardPage() {
  const { user } = useAuth()
  const { analyses, isLoading, error, retry } = useRecentAnalyses()

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title={user?.name ? `Welcome back, ${user.name}` : 'Welcome back'}
        description="An overview of your recent analyses."
        actions={
          <div className="flex gap-2">
            <Link
              to={ROUTES.patients}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            >
              View patients
            </Link>
            <Link
              to={ROUTES.upload}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            >
              Start new analysis
            </Link>
          </div>
        }
      />

      <section aria-labelledby="recent-analyses-heading" className="flex flex-col gap-4">
        <h2 id="recent-analyses-heading" className="text-lg font-semibold text-slate-900">
          Recent analyses
        </h2>

        {isLoading && <LoadingSpinner label="Loading your analyses" />}

        {!isLoading && error && (
          <ErrorState title="Couldn't load your analyses" message={error} onRetry={retry} />
        )}

        {!isLoading && !error && analyses.length === 0 && <DashboardEmptyState />}

        {!isLoading && !error && analyses.length > 0 && <RecentAnalysesList analyses={analyses} />}
      </section>
    </div>
  )
}
