import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DashboardPage } from '@/pages/DashboardPage'
import { useAuth } from '@/hooks/useAuth'
import { listRecentAnalyses } from '@/api/analyses'
import type { AnalysisSummary } from '@/types/api'

vi.mock('@/hooks/useAuth')
vi.mock('@/api/analyses')

const mockedUseAuth = vi.mocked(useAuth)
const mockedListRecentAnalyses = vi.mocked(listRecentAnalyses)

const sampleAnalysis: AnalysisSummary = {
  id: 42,
  status: 'completed',
  created_at: '2026-01-01T12:00:00Z',
  completed_at: '2026-01-01T12:05:00Z',
  error_message: null,
  summary: 'Reconciliation completed with 1 finding.',
  document_count: 2,
  total_findings: 1,
  high_severity_findings: 1,
  medium_severity_findings: 0,
  low_severity_findings: 0,
  provider: 'gemini',
  model_name: 'gemini-2.0-flash',
}

function renderDashboard() {
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <DashboardPage />
    </MemoryRouter>,
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    mockedListRecentAnalyses.mockReset()
    mockedUseAuth.mockReturnValue({
      user: { id: 1, email: 'a@example.com', name: 'Jane', created_at: '2026-01-01T00:00:00Z' },
      token: 'token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
    })
  })

  it('shows a welcome header and a primary action linking to Upload', async () => {
    mockedListRecentAnalyses.mockResolvedValue([])
    renderDashboard()

    expect(screen.getByRole('heading', { name: /Welcome back, Jane/ })).toBeInTheDocument()
    const uploadLink = screen.getByRole('link', { name: 'Start new analysis' })
    expect(uploadLink).toHaveAttribute('href', '/upload')

    await waitFor(() => expect(mockedListRecentAnalyses).toHaveBeenCalled())
  })

  it('shows a loading state while analyses are being fetched', () => {
    mockedListRecentAnalyses.mockReturnValue(new Promise(() => {}))
    renderDashboard()

    expect(screen.getByRole('status')).toHaveTextContent('Loading your analyses')
  })

  it('shows the empty state with a call to action when there are no analyses', async () => {
    mockedListRecentAnalyses.mockResolvedValue([])
    renderDashboard()

    expect(await screen.findByText('No analyses yet')).toBeInTheDocument()
    const startLink = screen.getByRole('link', { name: 'Start your first analysis' })
    expect(startLink).toHaveAttribute('href', '/upload')
  })

  it('renders a recent analysis with its key fields and links to the detail page', async () => {
    mockedListRecentAnalyses.mockResolvedValue([sampleAnalysis])
    renderDashboard()

    // Status is asserted via the link's accessible name, since the visible
    // "Completed" status badge and the "Completed" stat label (for
    // completed_at) are two separate, legitimately identical-looking
    // pieces of text on the same card.
    const cardLink = await screen.findByRole('link', { name: /status: Completed/ })
    expect(cardLink).toHaveAttribute('href', '/analyses/42')
    expect(screen.getByText('Reconciliation completed with 1 finding.')).toBeInTheDocument()
    expect(screen.getByText('Documents')).toBeInTheDocument()
    expect(screen.getAllByText('2')).toHaveLength(1) // document_count
  })

  it('shows an error state with a retry action when the request fails, and recovers on retry', async () => {
    mockedListRecentAnalyses.mockRejectedValueOnce({
      status: 500,
      message: 'Unable to reach the server.',
    })
    mockedListRecentAnalyses.mockResolvedValueOnce([sampleAnalysis])

    const user = userEvent.setup()
    renderDashboard()

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to reach the server.')

    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('link', { name: /status: Completed/ })).toBeInTheDocument()
    expect(mockedListRecentAnalyses).toHaveBeenCalledTimes(2)
  })
})
