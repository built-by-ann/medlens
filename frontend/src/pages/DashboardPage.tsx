import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { Card } from '@/components/common/Card'
import { useAuth } from '@/hooks/useAuth'
import { ROUTES } from '@/routes/paths'

// As of Sprint 3.5 (Issue #130), analyses are scoped to a patient - there is
// no longer a single "all of this user's recent analyses" feed to show
// here, since each patient now has its own analysis history (see
// PatientAnalysesPage). This page is intentionally a lightweight landing
// spot pointing at Patients rather than a rebuilt cross-patient dashboard.
export function DashboardPage() {
  const { user } = useAuth()

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title={user?.name ? `Welcome back, ${user.name}` : 'Welcome back'}
        description="MedLens compares medication information across a patient's clinical documents and flags potential inconsistencies for review."
      />

      <Card className="flex flex-col items-start gap-4">
        <p className="text-sm text-slate-600">
          Analyses, documents, and medications are all managed from a patient's page. Select a
          patient to get started, or add a new one.
        </p>
        <Link
          to={ROUTES.patients}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          View patients
        </Link>
      </Card>
    </div>
  )
}
