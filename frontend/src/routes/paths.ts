export const ROUTES = {
  home: '/',
  login: '/login',
  signup: '/signup',
  dashboard: '/dashboard',
  upload: '/upload',
  medications: '/medications',
  analysisDetail: '/analyses/:id',
} as const

export function analysisDetailPath(analysisId: string | number): string {
  return `/analyses/${analysisId}`
}
