import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { StartAnalysisDialog } from '@/components/dashboard/StartAnalysisDialog'
import type { Patient } from '@/types/api'

function makePatient(overrides: Partial<Patient> = {}): Patient {
  return {
    id: 1,
    user_id: 1,
    first_name: 'Jane',
    last_name: 'Doe',
    date_of_birth: '1980-05-14',
    external_mrn: null,
    status: 'active',
    notes: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    ...overrides,
  }
}

const jane = makePatient({ id: 1, first_name: 'Jane', last_name: 'Doe' })
const john = makePatient({
  id: 2,
  first_name: 'John',
  last_name: 'Roe',
  external_mrn: 'MRN-002',
})

describe('StartAnalysisDialog', () => {
  it('renders nothing accessible when closed', () => {
    render(
      <StartAnalysisDialog
        isOpen={false}
        patients={[jane]}
        onClose={vi.fn()}
        onSelectPatient={vi.fn()}
      />,
    )

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('lists every patient by name when open, showing an MRN only for patients that have one', () => {
    render(
      <StartAnalysisDialog
        isOpen
        patients={[jane, john]}
        onClose={vi.fn()}
        onSelectPatient={vi.fn()}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: 'Start an analysis' })
    expect(dialog).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Jane Doe/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /John Roe/ })).toHaveTextContent('MRN-002')
    expect(screen.getByRole('button', { name: /Jane Doe/ })).not.toHaveTextContent('MRN')
  })

  it('filters the patient list as the user searches, reusing the same search everywhere else uses', async () => {
    const user = userEvent.setup()
    render(
      <StartAnalysisDialog
        isOpen
        patients={[jane, john]}
        onClose={vi.fn()}
        onSelectPatient={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText('Search patients'), 'John')

    expect(screen.getByRole('button', { name: /John Roe/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Jane Doe/ })).not.toBeInTheDocument()
  })

  it('shows a message when no patient matches the search', async () => {
    const user = userEvent.setup()
    render(
      <StartAnalysisDialog
        isOpen
        patients={[jane, john]}
        onClose={vi.fn()}
        onSelectPatient={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText('Search patients'), 'Nobody')

    expect(screen.getByText('No patients match your search.')).toBeInTheDocument()
  })

  it('calls onSelectPatient with the chosen patient when a row is clicked', async () => {
    const onSelectPatient = vi.fn()
    const user = userEvent.setup()
    render(
      <StartAnalysisDialog
        isOpen
        patients={[jane, john]}
        onClose={vi.fn()}
        onSelectPatient={onSelectPatient}
      />,
    )

    await user.click(screen.getByRole('button', { name: /John Roe/ }))

    expect(onSelectPatient).toHaveBeenCalledTimes(1)
    expect(onSelectPatient).toHaveBeenCalledWith(john)
  })

  it('calls onClose when Cancel is clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <StartAnalysisDialog isOpen patients={[jane]} onClose={onClose} onSelectPatient={vi.fn()} />,
    )

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('calls onClose when the backdrop (the dialog element itself, outside its content) is clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <StartAnalysisDialog isOpen patients={[jane]} onClose={onClose} onSelectPatient={vi.fn()} />,
    )

    await user.click(screen.getByRole('dialog'))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('does not call onClose when clicking inside the dialog content', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <StartAnalysisDialog isOpen patients={[jane]} onClose={onClose} onSelectPatient={vi.fn()} />,
    )

    await user.click(screen.getByText('Choose a patient to build it for.'))

    expect(onClose).not.toHaveBeenCalled()
  })

  it('clears a previous search term each time it reopens', async () => {
    const user = userEvent.setup()
    const { rerender } = render(
      <StartAnalysisDialog
        isOpen
        patients={[jane, john]}
        onClose={vi.fn()}
        onSelectPatient={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText('Search patients'), 'John')
    expect(screen.queryByRole('button', { name: /Jane Doe/ })).not.toBeInTheDocument()

    rerender(
      <StartAnalysisDialog
        isOpen={false}
        patients={[jane, john]}
        onClose={vi.fn()}
        onSelectPatient={vi.fn()}
      />,
    )
    rerender(
      <StartAnalysisDialog
        isOpen
        patients={[jane, john]}
        onClose={vi.fn()}
        onSelectPatient={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('Search patients')).toHaveValue('')
    expect(screen.getByRole('button', { name: /Jane Doe/ })).toBeInTheDocument()
  })
})
