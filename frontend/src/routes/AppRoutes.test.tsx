import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppRoutes } from '@/routes/AppRoutes'
import { useAuth } from '@/hooks/useAuth'
import { getPatient, listPatients } from '@/api/patients'
import { listMedications } from '@/api/medications'
import { listAnalyses } from '@/api/analyses'

vi.mock('@/hooks/useAuth')

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    getPatient: vi.fn(),
    listPatients: vi.fn(),
  }
})

vi.mock('@/api/medications', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/medications')>()

  return { ...actual, listMedications: vi.fn() }
})

vi.mock('@/api/analyses', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/analyses')>()

  return { ...actual, listAnalyses: vi.fn() }
})

const mockedUseAuth = vi.mocked(useAuth)
const mockedGetPatient = vi.mocked(getPatient)
const mockedListPatients = vi.mocked(listPatients)
const mockedListMedications = vi.mocked(listMedications)
const mockedListAnalyses = vi.mocked(listAnalyses)

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )
}

describe('AppRoutes legacy route redirects', () => {
  beforeEach(() => {
    mockedGetPatient.mockReset()
    mockedListPatients.mockReset()
    mockedListMedications.mockReset()
    mockedListAnalyses.mockReset()
    mockedListPatients.mockResolvedValue([])
    mockedListMedications.mockResolvedValue([])
    mockedListAnalyses.mockResolvedValue([])
    mockedGetPatient.mockReturnValue(new Promise(() => {}))
    mockedUseAuth.mockReturnValue({
      user: {
        id: 1,
        email: 'a@example.com',
        name: 'Jane',
        username: null,
        created_at: '2026-01-01T00:00:00Z',
      },
      token: 'token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      setUser: vi.fn(),
      sessionExpiredMessage: null,
      clearSessionExpiredMessage: vi.fn(),
    })
  })

  it('redirects the pre-Sprint-3.5 global /upload route to Patients', async () => {
    renderAt('/upload')

    expect(await screen.findByRole('heading', { name: 'Patients' })).toBeInTheDocument()
  })

  it('redirects the pre-Sprint-3.5 global /analyses/:id route to Patients', async () => {
    renderAt('/analyses/42')

    expect(await screen.findByRole('heading', { name: 'Patients' })).toBeInTheDocument()
  })

  it('renders UploadPage for the new patient-scoped upload route', () => {
    renderAt('/patients/7/upload')

    expect(screen.getByRole('status')).toHaveTextContent('Loading patient')
  })

  it('renders PatientAnalysesPage for the new patient-scoped analyses route', () => {
    renderAt('/patients/7/analyses')

    expect(screen.getByRole('status')).toHaveTextContent('Loading patient')
  })
})
