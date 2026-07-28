export const ROUTES = {
  home: '/',
  login: '/login',
  signup: '/signup',
  dashboard: '/dashboard',
  upload: '/upload',
  patients: '/patients',
  newPatient: '/patients/new',
  patientDetail: '/patients/:patientId',
  patientEdit: '/patients/:patientId/edit',
  patientMedications: '/patients/:patientId/medications',
  analysisDetail: '/analyses/:id',
} as const

export function analysisDetailPath(analysisId: string | number): string {
  return `/analyses/${analysisId}`
}

export function patientDetailPath(patientId: string | number): string {
  return `/patients/${patientId}`
}

export function patientEditPath(patientId: string | number): string {
  return `/patients/${patientId}/edit`
}

export function patientMedicationsPath(patientId: string | number): string {
  return `/patients/${patientId}/medications`
}
