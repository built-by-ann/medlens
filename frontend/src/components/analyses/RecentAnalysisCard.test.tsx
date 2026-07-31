import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { RecentAnalysisCard } from '@/components/analyses/RecentAnalysisCard'
import type { AnalysisSummary } from '@/types/api'

function makeAnalysis(overrides: Partial<AnalysisSummary> = {}): AnalysisSummary {
  return {
    id: 5,
    patient_id: 7,
    status: 'completed',
    created_at: '2026-01-01T12:00:00Z',
    completed_at: '2026-01-01T12:05:00Z',
    error_message: null,
    summary: null,
    document_count: 2,
    total_findings: 3,
    high_severity_findings: 1,
    medium_severity_findings: 1,
    low_severity_findings: 1,
    provider: null,
    model_name: null,
    ...overrides,
  }
}

function renderCard(props: Partial<Parameters<typeof RecentAnalysisCard>[0]> = {}) {
  return render(
    <MemoryRouter>
      <RecentAnalysisCard analysis={makeAnalysis()} {...props} />
    </MemoryRouter>,
  )
}

describe('RecentAnalysisCard', () => {
  it('links to the analysis detail page for this patient and analysis', () => {
    renderCard({ analysis: makeAnalysis({ patient_id: 7, id: 5 }) })

    expect(screen.getByRole('link')).toHaveAttribute('href', '/patients/7/analyses/5')
  })

  it("does not show a patient name, and the link's name omits one, when patientName is unset", () => {
    renderCard()

    expect(screen.getByRole('link', { name: /^View analysis from/ })).toBeInTheDocument()
  })

  it("shows the patient name and includes it in the link's accessible name when provided", () => {
    renderCard({ patientName: 'Jane Doe' })

    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /View analysis for Jane Doe from/ }),
    ).toBeInTheDocument()
  })

  it('shows the status label and summary when present', () => {
    renderCard({
      analysis: makeAnalysis({ status: 'processing', summary: 'Reviewed 2 documents.' }),
    })

    expect(screen.getByText('Processing')).toBeInTheDocument()
    expect(screen.getByText('Reviewed 2 documents.')).toBeInTheDocument()
  })

  it('shows an announced failure notice only for a failed analysis with an error message', () => {
    const { rerender } = render(
      <MemoryRouter>
        <RecentAnalysisCard
          analysis={makeAnalysis({ status: 'failed', error_message: 'The AI provider timed out.' })}
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('The AI provider timed out.')

    rerender(
      <MemoryRouter>
        <RecentAnalysisCard analysis={makeAnalysis({ status: 'completed', error_message: null })} />
      </MemoryRouter>,
    )

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('renders no delete button when onDelete is not provided', () => {
    renderCard()

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('calls onDelete with the analysis id when the delete button is clicked', async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderCard({ analysis: makeAnalysis({ id: 42 }), onDelete })

    await user.click(screen.getByRole('button', { name: /Delete analysis from/ }))

    expect(onDelete).toHaveBeenCalledWith(42)
  })

  it('shows an error and re-enables the delete button when deletion fails', async () => {
    const onDelete = vi.fn().mockRejectedValue({ status: 500, message: 'Could not delete.' })
    const user = userEvent.setup()
    renderCard({ onDelete })

    const deleteButton = screen.getByRole('button', { name: /Delete analysis from/ })
    await user.click(deleteButton)

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not delete.')
    expect(deleteButton).toBeEnabled()
    expect(deleteButton).toHaveTextContent('Delete')
  })
})
