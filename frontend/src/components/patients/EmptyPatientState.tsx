import { Link } from 'react-router-dom'
import { Card } from '@/components/common/Card'
import { ROUTES } from '@/routes/paths'

interface EmptyPatientStateProps {
  hasActivePatients: boolean
}

/**
 * hasActivePatients distinguishes "no patients at all" (show a create CTA)
 * from "a search matched nothing" (the unfiltered list is non-empty).
 */
export function EmptyPatientState({ hasActivePatients }: EmptyPatientStateProps) {
  if (hasActivePatients) {
    return <p className="text-sm text-slate-500">No patients match your search.</p>
  }

  return (
    <Card className="flex flex-col items-center gap-3 py-10 text-center">
      <h3 className="text-sm font-semibold text-slate-900">No patients yet</h3>
      <p className="max-w-md text-sm text-slate-600">
        Add your first patient to start tracking their medications, documents, and analyses.
      </p>
      <Link
        to={ROUTES.newPatient}
        className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      >
        Add a patient
      </Link>
    </Card>
  )
}
