import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { BackButton } from '@/components/common/BackButton'

function renderBackButton(initialEntries: string[]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/previous" element={<div>Previous page</div>} />
        <Route path="/fallback" element={<div>Fallback page</div>} />
        <Route path="/current" element={<BackButton to="/fallback" label="Jane Doe" />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('BackButton', () => {
  it('renders a descriptive accessible name of "Back to {label}"', () => {
    renderBackButton(['/current'])

    expect(screen.getByRole('button', { name: 'Back to Jane Doe' })).toBeInTheDocument()
  })

  it('hides the decorative arrow from assistive technology', () => {
    renderBackButton(['/current'])

    const arrow = screen.getByText('←')
    expect(arrow).toHaveAttribute('aria-hidden', 'true')
  })

  it('returns to the previous page when it was reached via in-app navigation', async () => {
    const user = userEvent.setup()
    renderBackButton(['/previous', '/current'])

    await user.click(screen.getByRole('button', { name: 'Back to Jane Doe' }))

    expect(await screen.findByText('Previous page')).toBeInTheDocument()
  })

  it('falls back to the given route when there is no in-app history to return to', async () => {
    const user = userEvent.setup()
    renderBackButton(['/current'])

    await user.click(screen.getByRole('button', { name: 'Back to Jane Doe' }))

    expect(await screen.findByText('Fallback page')).toBeInTheDocument()
  })
})
