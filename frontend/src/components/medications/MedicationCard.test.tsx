import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MedicationCard } from '@/components/medications/MedicationCard'
import type { Medication } from '@/types/api'

function makeMedication(overrides: Partial<Medication> = {}): Medication {
  return {
    id: 3,
    patient_id: 7,
    medication_name: 'Lisinopril',
    dose: '10mg',
    route: 'oral',
    frequency: 'once daily',
    status: 'active',
    source: 'patient_reported',
    notes: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    ...overrides,
  }
}

describe('MedicationCard', () => {
  it('shows the medication name, dosage details, and notes when present', () => {
    render(
      <MedicationCard
        medication={makeMedication({ notes: 'Take with food.' })}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    )

    expect(screen.getByText('Lisinopril')).toBeInTheDocument()
    expect(screen.getByText('10mg')).toBeInTheDocument()
    expect(screen.getByText('oral')).toBeInTheDocument()
    expect(screen.getByText('once daily')).toBeInTheDocument()
    expect(screen.getByText('active')).toBeInTheDocument()
    expect(screen.getByText('Take with food.')).toBeInTheDocument()
  })

  it('omits the notes line when there are none', () => {
    render(
      <MedicationCard
        medication={makeMedication({ notes: null })}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    )

    expect(screen.queryByText('Take with food.')).not.toBeInTheDocument()
  })

  it('switches to an edit form pre-filled with the current values, and back on Cancel', async () => {
    const user = userEvent.setup()
    render(<MedicationCard medication={makeMedication()} onEdit={vi.fn()} onDelete={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Edit' }))

    expect(screen.getByLabelText('Medication name')).toHaveValue('Lisinopril')
    expect(screen.getByLabelText('Dosage')).toHaveValue('10mg')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByLabelText('Medication name')).not.toBeInTheDocument()
    expect(screen.getByText('Lisinopril')).toBeInTheDocument()
  })

  it('shows validation errors and does not call onEdit when a required field is cleared', async () => {
    const onEdit = vi.fn()
    const user = userEvent.setup()
    render(<MedicationCard medication={makeMedication()} onEdit={onEdit} onDelete={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Edit' }))
    await user.clear(screen.getByLabelText('Medication name'))
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Medication name is required.')).toBeInTheDocument()
    expect(onEdit).not.toHaveBeenCalled()
  })

  it('saves the edited values and returns to the display view on success', async () => {
    const updated = makeMedication({ dose: '20mg' })
    const onEdit = vi.fn().mockResolvedValue(updated)
    const user = userEvent.setup()
    render(<MedicationCard medication={makeMedication()} onEdit={onEdit} onDelete={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Edit' }))
    await user.clear(screen.getByLabelText('Dosage'))
    await user.type(screen.getByLabelText('Dosage'), '20mg')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    await screen.findByText('Lisinopril')
    expect(onEdit).toHaveBeenCalledWith(3, expect.objectContaining({ dose: '20mg' }))
    expect(screen.queryByLabelText('Medication name')).not.toBeInTheDocument()
  })

  it('shows an error and keeps the edit form open with entered values when saving fails', async () => {
    const onEdit = vi.fn().mockRejectedValue({ status: 500, message: 'Could not save.' })
    const user = userEvent.setup()
    render(<MedicationCard medication={makeMedication()} onEdit={onEdit} onDelete={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Edit' }))
    await user.clear(screen.getByLabelText('Dosage'))
    await user.type(screen.getByLabelText('Dosage'), '20mg')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not save.')
    expect(screen.getByLabelText('Dosage')).toHaveValue('20mg')
  })

  it('calls onDelete with the medication id when Delete is clicked', async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined)
    const user = userEvent.setup()
    render(
      <MedicationCard
        medication={makeMedication({ id: 9 })}
        onEdit={vi.fn()}
        onDelete={onDelete}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Delete Lisinopril' }))

    expect(onDelete).toHaveBeenCalledWith(9)
  })

  it('shows an error and re-enables Delete when deleting fails', async () => {
    const onDelete = vi.fn().mockRejectedValue({ status: 500, message: 'Could not delete.' })
    const user = userEvent.setup()
    render(<MedicationCard medication={makeMedication()} onEdit={vi.fn()} onDelete={onDelete} />)

    await user.click(screen.getByRole('button', { name: 'Delete Lisinopril' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not delete.')
    expect(screen.getByRole('button', { name: 'Delete Lisinopril' })).toBeEnabled()
  })
})
