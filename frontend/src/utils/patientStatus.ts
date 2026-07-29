export const PATIENT_STATUS_LABELS: Record<string, string> = {
  active: 'Active',
  archived: 'Archived',
}

export function patientStatusLabel(status: string): string {
  return PATIENT_STATUS_LABELS[status] ?? status
}
