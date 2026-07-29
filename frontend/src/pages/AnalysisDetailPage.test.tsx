import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AnalysisDetailPage } from '@/pages/AnalysisDetailPage'

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/patients/7/analyses/42']}>
      <Routes>
        <Route path="/patients/:patientId/analyses/:analysisId" element={<AnalysisDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AnalysisDetailPage', () => {
  it('shows the analysis id from the route in the heading', () => {
    renderPage()

    expect(screen.getByRole('heading', { name: 'Analysis #42' })).toBeInTheDocument()
  })

  it('links back to this patient’s analysis history', () => {
    renderPage()

    expect(screen.getByRole('link', { name: /Back to analyses/ })).toHaveAttribute(
      'href',
      '/patients/7/analyses',
    )
  })
})
