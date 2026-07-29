import { Link } from 'react-router-dom'
import { ROUTES, patientDetailPath } from '@/routes/paths'
import type { Patient } from '@/types/api'

export interface BreadcrumbTrailItem {
  label: string
  to?: string
}

interface PatientBreadcrumbProps {
  patient: Patient
  trail?: BreadcrumbTrailItem[]
}

/**
 * Consistent "Patients / {name} / ..." trail for every page nested under a
 * patient, so a provider always knows which patient they're viewing and can
 * get back in one click - never a dead end. The last crumb is always the
 * current page: rendered as plain text with aria-current="page", never a
 * link to itself.
 */
export function PatientBreadcrumb({ patient, trail = [] }: PatientBreadcrumbProps) {
  const crumbs: BreadcrumbTrailItem[] = [
    { label: 'Patients', to: ROUTES.patients },
    { label: `${patient.first_name} ${patient.last_name}`, to: patientDetailPath(patient.id) },
    ...trail,
  ]

  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex flex-wrap items-center gap-1 text-sm text-slate-500">
        {crumbs.map((crumb, index) => {
          const isCurrent = index === crumbs.length - 1

          return (
            <li key={`${crumb.label}-${index}`} className="flex items-center gap-1">
              {index > 0 && (
                <span aria-hidden="true" className="text-slate-300">
                  /
                </span>
              )}
              {isCurrent || !crumb.to ? (
                <span aria-current={isCurrent ? 'page' : undefined} className="text-slate-700">
                  {crumb.label}
                </span>
              ) : (
                <Link to={crumb.to} className="hover:text-slate-700 hover:underline">
                  {crumb.label}
                </Link>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
