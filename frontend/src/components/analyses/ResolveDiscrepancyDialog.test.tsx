import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import {
  ResolveDiscrepancyDialog,
  type ResolveDiscrepancyTarget,
} from '@/components/analyses/ResolveDiscrepancyDialog'
import type { DiscrepancyActionDescriptor } from '@/utils/discrepancyResolutionActions'

const confirmOnlyAction: DiscrepancyActionDescriptor = {
  key: 'update',
  label: 'Update Medication',
  action: 'update_medication',
  editable: false,
  fields: [{ key: 'dose', label: 'Dose', value: '10 mg' }],
  description: 'Update dose to "10 mg".',
}

const editableAction: DiscrepancyActionDescriptor = {
  key: 'add',
  label: 'Add Medication',
  action: 'add_medication',
  editable: true,
  fields: [
    { key: 'medication_name', label: 'Medication name', value: 'Lisinopril' },
    { key: 'dose', label: 'Dose', value: '' },
    { key: 'route', label: 'Route', value: 'oral' },
    { key: 'frequency', label: 'Frequency', value: 'once daily' },
    { key: 'status', label: 'Status', value: 'active' },
  ],
  description: "Add this medication to the patient's medication list.",
}

const dismissAction: DiscrepancyActionDescriptor = {
  key: 'dismiss',
  label: 'Dismiss',
  action: 'dismiss',
  editable: false,
  fields: [],
  description: 'Dismiss this finding without changing the medication list.',
}

function makeTarget(action: DiscrepancyActionDescriptor): ResolveDiscrepancyTarget {
  return { discrepancyId: 1, medicationName: 'Lisinopril', action }
}

describe('ResolveDiscrepancyDialog', () => {
  it('renders nothing accessible when target is null', () => {
    render(
      <ResolveDiscrepancyDialog
        target={null}
        isSubmitting={false}
        error={null}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    )

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows the action label, medication name, and description', () => {
    render(
      <ResolveDiscrepancyDialog
        target={makeTarget(confirmOnlyAction)}
        isSubmitting={false}
        error={null}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    )

    expect(
      screen.getByRole('dialog', { name: 'Update Medication: Lisinopril' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Update dose to "10 mg".')).toBeInTheDocument()
  })

  it('renders no editable medication fields for a confirm-only action', () => {
    render(
      <ResolveDiscrepancyDialog
        target={makeTarget(confirmOnlyAction)}
        isSubmitting={false}
        error={null}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    )

    expect(screen.queryByLabelText('Dose')).not.toBeInTheDocument()
    // The note field is always present, confirm-only or not.
    expect(screen.getByLabelText('Note (optional)')).toBeInTheDocument()
  })

  it('renders every field as an editable input, pre-filled, for an editable action', () => {
    render(
      <ResolveDiscrepancyDialog
        target={makeTarget(editableAction)}
        isSubmitting={false}
        error={null}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    )

    expect(screen.getByLabelText(/Medication name/)).toHaveValue('Lisinopril')
    expect(screen.getByLabelText(/Route/)).toHaveValue('oral')
    expect(screen.getByLabelText(/Dose/)).toHaveValue('')
  })

  it('disables Confirm while a required field (add_medication) is empty', () => {
    render(
      <ResolveDiscrepancyDialog
        target={makeTarget(editableAction)}
        isSubmitting={false}
        error={null}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    )

    // dose is required for add_medication and starts empty.
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeDisabled()
  })

  it('enables Confirm once every required field is filled', async () => {
    const user = userEvent.setup()
    render(
      <ResolveDiscrepancyDialog
        target={makeTarget(editableAction)}
        isSubmitting={false}
        error={null}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText(/Dose/), '10 mg')

    expect(screen.getByRole('button', { name: 'Confirm' })).toBeEnabled()
  })

  it('never disables Confirm for a confirm-only or dismiss action, nothing is required', () => {
    render(
      <ResolveDiscrepancyDialog
        target={makeTarget(dismissAction)}
        isSubmitting={false}
        error={null}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: 'Confirm' })).toBeEnabled()
  })

  it('calls onConfirm with the built payload, including edited field values and a note', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    render(
      <ResolveDiscrepancyDialog
        target={makeTarget(editableAction)}
        isSubmitting={false}
        error={null}
        onCancel={vi.fn()}
        onConfirm={onConfirm}
      />,
    )

    await user.type(screen.getByLabelText(/Dose/), '10 mg')
    await user.type(screen.getByLabelText('Note (optional)'), 'Confirmed by phone.')
    await user.click(screen.getByRole('button', { name: 'Confirm' }))

    expect(onConfirm).toHaveBeenCalledWith({
      action: 'add_medication',
      medication_name: 'Lisinopril',
      dose: '10 mg',
      route: 'oral',
      frequency: 'once daily',
      status: 'active',
      note: 'Confirmed by phone.',
    })
  })

  it('calls onConfirm with just the action for dismiss when nothing else is filled', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    render(
      <ResolveDiscrepancyDialog
        target={makeTarget(dismissAction)}
        isSubmitting={false}
        error={null}
        onCancel={vi.fn()}
        onConfirm={onConfirm}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Confirm' }))

    expect(onConfirm).toHaveBeenCalledWith({ action: 'dismiss' })
  })

  it('calls onCancel when Cancel is clicked', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    render(
      <ResolveDiscrepancyDialog
        target={makeTarget(dismissAction)}
        isSubmitting={false}
        error={null}
        onCancel={onCancel}
        onConfirm={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('calls onCancel when the backdrop is clicked', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    render(
      <ResolveDiscrepancyDialog
        target={makeTarget(dismissAction)}
        isSubmitting={false}
        error={null}
        onCancel={onCancel}
        onConfirm={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('dialog'))

    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('shows the error message when resolution fails', () => {
    render(
      <ResolveDiscrepancyDialog
        target={makeTarget(dismissAction)}
        isSubmitting={false}
        error="Discrepancy has already been resolved"
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('Discrepancy has already been resolved')
  })

  it('disables Cancel/Confirm and shows a saving label while submitting', () => {
    render(
      <ResolveDiscrepancyDialog
        target={makeTarget(dismissAction)}
        isSubmitting
        error={null}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Saving...' })).toBeDisabled()
  })

  it('resets field values and note each time it opens for a new target', async () => {
    const user = userEvent.setup()
    const { rerender } = render(
      <ResolveDiscrepancyDialog
        target={makeTarget(editableAction)}
        isSubmitting={false}
        error={null}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    )

    await user.clear(screen.getByLabelText(/Route/))
    await user.type(screen.getByLabelText(/Route/), 'IV')
    await user.type(screen.getByLabelText('Note (optional)'), 'A note.')

    rerender(
      <ResolveDiscrepancyDialog
        target={null}
        isSubmitting={false}
        error={null}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    )
    rerender(
      <ResolveDiscrepancyDialog
        target={makeTarget(editableAction)}
        isSubmitting={false}
        error={null}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    )

    expect(screen.getByLabelText(/Route/)).toHaveValue('oral')
    expect(screen.getByLabelText('Note (optional)')).toHaveValue('')
  })
})
