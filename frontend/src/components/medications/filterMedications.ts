import type { Medication } from '@/types/api'

/**
 * Client-side search over a patient's already-fetched medications (no
 * backend search parameter exists for this list, same reasoning as
 * filterPatients.ts/filterClinicalDocuments.ts). Matches medication name,
 * dose, route, frequency, or status, case-insensitively. Returns a new
 * array and never mutates `medications`.
 */
export function filterMedications(medications: Medication[], searchTerm: string): Medication[] {
  const normalized = searchTerm.trim().toLowerCase()

  if (!normalized) {
    return medications
  }

  return medications.filter((medication) => {
    const name = medication.medication_name.toLowerCase()
    const dose = medication.dose.toLowerCase()
    const route = medication.route.toLowerCase()
    const frequency = medication.frequency.toLowerCase()
    const status = medication.status.toLowerCase()

    return (
      name.includes(normalized) ||
      dose.includes(normalized) ||
      route.includes(normalized) ||
      frequency.includes(normalized) ||
      status.includes(normalized)
    )
  })
}
