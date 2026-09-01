import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MedicationDiscrepancyCard } from '@/components/analyses/MedicationDiscrepancyCard'
import type { MedicationDiscrepancy } from '@/types/api'

function makeDiscrepancy(overrides: Partial<MedicationDiscrepancy> = {}): MedicationDiscrepancy {
  return {
    id: 1,
    analysis_id: 7,
    medication_id: null,
    medication_mention_id: 9,
    discrepancy_type: 'missing_from_medication_list',
    severity: 'high',
    title: 'Lisinopril not found in medication list',
    ai_explanation: 'Lisinopril is mentioned but not on the medication list.',
    recommendation: null,
    expected_value: null,
    observed_value: 'Lisinopril',
    resolution_status: 'open',
    resolution_action: null,
    resolved_at: null,
    resolution_note: null,
    resolved_by: null,
    created_at: '2026-01-01T12:00:00Z',
    updated_at: null,
    medication: null,
    medication_mention: {
      id: 9,
      medication_name: 'Lisinopril',
      dose: '10 mg',
      route: 'oral',
      frequency: 'once daily',
      status: 'active',
      context_text: 'Patient reports taking Lisinopril 10 mg daily.',
      clinical_document: { id: 3, title: 'Visit Note', document_type: 'visit_note' },
    },
    ...overrides,
  }
}

describe('MedicationDiscrepancyCard', () => {
  it('renders action buttons matching the discrepancy type when open and a handler is provided', () => {
    render(<MedicationDiscrepancyCard discrepancy={makeDiscrepancy()} onResolveAction={vi.fn()} />)

    expect(screen.getByRole('button', { name: /Add Medication/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Dismiss/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Update Medication/ })).not.toBeInTheDocument()
  })

  it('button labels include the medication name for a descriptive accessible name', () => {
    render(<MedicationDiscrepancyCard discrepancy={makeDiscrepancy()} onResolveAction={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Add Medication: Lisinopril' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Dismiss: Lisinopril' })).toBeInTheDocument()
  })

  it('calls onResolveAction with the discrepancy id, medication name, and chosen action', async () => {
    const user = userEvent.setup()
    const onResolveAction = vi.fn()
    render(
      <MedicationDiscrepancyCard
        discrepancy={makeDiscrepancy({ id: 42 })}
        onResolveAction={onResolveAction}
      />,
    )

    await user.click(screen.getByRole('button', { name: /Add Medication/ }))

    expect(onResolveAction).toHaveBeenCalledTimes(1)
    const target = onResolveAction.mock.calls[0]![0]
    expect(target.discrepancyId).toBe(42)
    expect(target.medicationName).toBe('Lisinopril')
    expect(target.action.action).toBe('add_medication')
  })

  it('renders no action buttons when no handler is provided (read-only)', () => {
    render(<MedicationDiscrepancyCard discrepancy={makeDiscrepancy()} />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('renders no action buttons once a discrepancy is resolved, editing stays disabled', () => {
    render(
      <MedicationDiscrepancyCard
        discrepancy={makeDiscrepancy({
          resolution_status: 'resolved',
          resolution_action: 'add_medication',
          resolved_at: '2026-01-02T09:30:00Z',
        })}
        onResolveAction={vi.fn()}
      />,
    )

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('shows who resolved a discrepancy and when', () => {
    render(
      <MedicationDiscrepancyCard
        discrepancy={makeDiscrepancy({
          resolution_status: 'resolved',
          resolution_action: 'add_medication',
          resolved_at: '2026-01-02T09:30:00Z',
          resolved_by: { id: 3, name: 'Dr. Ann Lee', username: null, email: 'ann@example.com' },
        })}
      />,
    )

    // Not a bare `/Resolved/` match; ResolutionStatusBadge also renders the
    // word "Resolved" on its own, so the assertion has to include enough of
    // the sentence to be unambiguous.
    expect(screen.getByText(/Resolved by Dr\. Ann Lee/)).toBeInTheDocument()
  })

  it('prefers the resolver username over their name, when both are on file', () => {
    render(
      <MedicationDiscrepancyCard
        discrepancy={makeDiscrepancy({
          resolution_status: 'resolved',
          resolution_action: 'add_medication',
          resolved_at: '2026-01-02T09:30:00Z',
          resolved_by: { id: 3, name: 'Dr. Ann Lee', username: 'annlee', email: 'ann@example.com' },
        })}
      />,
    )

    expect(screen.getByText(/Resolved by annlee/)).toBeInTheDocument()
    expect(screen.queryByText(/Resolved by Dr\. Ann Lee/)).not.toBeInTheDocument()
  })

  it('falls back to the resolver name, then email, when no username is on file', () => {
    render(
      <MedicationDiscrepancyCard
        discrepancy={makeDiscrepancy({
          resolution_status: 'dismissed',
          resolution_action: 'dismiss',
          resolved_at: '2026-01-02T09:30:00Z',
          resolved_by: { id: 3, name: null, username: null, email: 'ann@example.com' },
        })}
      />,
    )

    expect(screen.getByText(/Dismissed by ann@example\.com/)).toBeInTheDocument()
  })

  it('shows the resolution note when present', () => {
    render(
      <MedicationDiscrepancyCard
        discrepancy={makeDiscrepancy({
          resolution_status: 'dismissed',
          resolution_action: 'dismiss',
          resolved_at: '2026-01-02T09:30:00Z',
          resolution_note: 'Confirmed with the patient by phone.',
        })}
      />,
    )

    expect(screen.getByText('Confirmed with the patient by phone.')).toBeInTheDocument()
  })

  it('does not render the resolution audit block while still open', () => {
    render(<MedicationDiscrepancyCard discrepancy={makeDiscrepancy()} />)

    expect(screen.queryByText(/Resolved/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Dismissed/)).not.toBeInTheDocument()
  })

  it('offers Mark Discontinued/Mark Active/Edit Manually/Dismiss for a status conflict', () => {
    render(
      <MedicationDiscrepancyCard
        discrepancy={makeDiscrepancy({
          discrepancy_type: 'discontinued_status_conflict',
          medication_mention_id: null,
          medication_id: 5,
          medication: {
            id: 5,
            patient_id: 1,
            medication_name: 'Lisinopril',
            dose: '10 mg',
            route: 'oral',
            frequency: 'once daily',
            status: 'active',
            source: 'patient_reported',
            notes: null,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: null,
          },
        })}
        onResolveAction={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: /Mark Discontinued/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Mark Active/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Edit Manually/ })).toBeInTheDocument()
  })
})
