import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ErrorState } from '@/components/common/ErrorState'

describe('ErrorState', () => {
  it('renders the title and message inside an alert region', () => {
    render(
      <ErrorState
        title="Couldn't load this patient"
        message="Unable to reach the server. Check your connection and try again."
        onRetry={() => {}}
      />,
    )

    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent("Couldn't load this patient")
    expect(alert).toHaveTextContent(
      'Unable to reach the server. Check your connection and try again.',
    )
  })

  it('calls onRetry when the retry button is clicked', async () => {
    const onRetry = vi.fn()
    const user = userEvent.setup()

    render(
      <ErrorState title="Couldn't load this patient" message="Server error." onRetry={onRetry} />,
    )
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('renders a fresh title and message when the props change, replacing the old ones', () => {
    const { rerender } = render(
      <ErrorState title="Couldn't load this patient" message="Server error." onRetry={() => {}} />,
    )

    rerender(
      <ErrorState title="Couldn't load medications" message="Network error." onRetry={() => {}} />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent("Couldn't load medications")
    expect(screen.queryByText("Couldn't load this patient")).not.toBeInTheDocument()
  })
})
