import type { Patient } from '@/types/api'

/**
 * "Recent patients" strategy for DashboardPage, in the priority order the
 * data actually supports:
 *
 * 1. Access timestamps ("last opened by this provider") - not tracked
 *    anywhere in this app, so not used.
 * 2. Recently updated - `Patient.updated_at` exists and is used here. It is
 *    only set once a patient row is actually edited (see
 *    `app/services/patient_service.py`), so it is `null` for any patient
 *    that has never been updated since creation.
 * 3. Creation date descending - the fallback for step 2's `null` case, and
 *    also happens to be the order `GET /patients` already returns rows in.
 *
 * `updated_at ?? created_at` combines steps 2 and 3 into a single sort: a
 * patient's "last touched" moment is its most recent edit, or its creation
 * if it's never been edited. Returns a new array (never mutates `patients`)
 * and does not refetch - this only reorders/slices data `usePatients()`
 * already loaded, so calling it introduces no extra requests.
 */
export function sortPatientsByRecentActivity(patients: Patient[], limit: number): Patient[] {
  function lastActivityTime(patient: Patient): number {
    return new Date(patient.updated_at ?? patient.created_at).getTime()
  }

  return [...patients].sort((a, b) => lastActivityTime(b) - lastActivityTime(a)).slice(0, limit)
}
