export const ROUTES = {
  home: '/',
  login: '/login',
  signup: '/signup',
  dashboard: '/dashboard',
  upload: '/upload',
  medications: '/medications',
  patients: '/patients',
  newPatient: '/patients/new',
  patientDetail: '/patients/:patientId',
  patientEdit: '/patients/:patientId/edit',
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
