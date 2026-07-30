import { BackButton } from '@/components/common/BackButton'
import {
  PatientBreadcrumb,
  type BreadcrumbTrailItem,
} from '@/components/patients/PatientBreadcrumb'
import type { Patient } from '@/types/api'

interface PatientPageNavProps {
  patient: Patient
  trail?: BreadcrumbTrailItem[]
  /** Logical parent route this page's Back action returns to as a fallback. */
  backTo: string
  /** Passed straight through to BackButton: renders as "Back to {backLabel}". */
  backLabel: string
}

/**
 * The shared navigation block for every page nested under a patient:
 * PatientBreadcrumb (the full "Patients / {name} / ..." trail) plus a
 * BackButton right underneath it. Bundling both here, rather than each page
 * composing them separately, is what keeps every patient-related page's
 * navigation identical instead of independently hand-rolled.
 */
export function PatientPageNav({ patient, trail, backTo, backLabel }: PatientPageNavProps) {
  return (
    <div className="flex flex-col gap-2">
      <PatientBreadcrumb patient={patient} trail={trail} />
      <BackButton to={backTo} label={backLabel} />
    </div>
  )
}
