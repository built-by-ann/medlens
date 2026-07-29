export const ROUTES = {
  home: '/',
  login: '/login',
  signup: '/signup',
  dashboard: '/dashboard',
  patients: '/patients',
  newPatient: '/patients/new',
  patientDetail: '/patients/:patientId',
  patientEdit: '/patients/:patientId/edit',
  patientMedications: '/patients/:patientId/medications',
  patientUpload: '/patients/:patientId/upload',
  patientAnalyses: '/patients/:patientId/analyses',
  patientSelectDocuments: '/patients/:patientId/analyses/select-documents',
  patientAnalysisProcessing: '/patients/:patientId/analyses/processing',
  patientAnalysisDetail: '/patients/:patientId/analyses/:analysisId',
  // Pre-Sprint-3.5 global routes, kept only as redirect targets (see
  // AppRoutes.tsx) so old links/bookmarks land somewhere useful instead of
  // a bare 404, now that upload and analyses are patient-scoped.
  legacyUpload: '/upload',
  legacyAnalysisDetail: '/analyses/:id',
} as const

export function patientDetailPath(patientId: string | number): string {
  return `/patients/${patientId}`
}

export function patientEditPath(patientId: string | number): string {
  return `/patients/${patientId}/edit`
}

export function patientMedicationsPath(patientId: string | number): string {
  return `/patients/${patientId}/medications`
}

export function patientUploadPath(patientId: string | number): string {
  return `/patients/${patientId}/upload`
}

export function patientAnalysesPath(patientId: string | number): string {
  return `/patients/${patientId}/analyses`
}

export function selectDocumentsPath(patientId: string | number): string {
  return `/patients/${patientId}/analyses/select-documents`
}

export function analysisProcessingPath(patientId: string | number): string {
  return `/patients/${patientId}/analyses/processing`
}

export function analysisDetailPath(
  patientId: string | number,
  analysisId: string | number,
): string {
  return `/patients/${patientId}/analyses/${analysisId}`
}
