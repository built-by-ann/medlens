import type { Patient } from '@/types/api'

/**
 * Client-side search: the backend's GET /patients has no search parameter,
 * so filtering happens here instead of a request. Matches first name, last
 * name, full name, or MRN, case-insensitively. Returns a new array (via
 * filter) and never mutates `patients`.
 */
export function filterPatients(patients: Patient[], searchTerm: string): Patient[] {
  const normalized = searchTerm.trim().toLowerCase()

  if (!normalized) {
    return patients
  }

  return patients.filter((patient) => {
    const firstName = patient.first_name.toLowerCase()
    const lastName = patient.last_name.toLowerCase()
    const fullName = `${firstName} ${lastName}`
    const mrn = patient.external_mrn?.toLowerCase() ?? ''

    return (
      firstName.includes(normalized) ||
      lastName.includes(normalized) ||
      fullName.includes(normalized) ||
      mrn.includes(normalized)
    )
  })
}
