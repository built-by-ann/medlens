import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { ComponentProps } from 'react'
import { PatientCard } from '@/components/patients/PatientCard'
import type { Patient } from '@/types/api'

function makePatient(overrides: Partial<Patient> = {}): Patient {
  return {
    id: 7,
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

function renderCard(props: Partial<ComponentProps<typeof PatientCard>> = {}) {
  const patient = props.patient ?? makePatient()
  return render(
    <MemoryRouter>
      <PatientCard patient={patient} onArchiveRequest={vi.fn()} {...props} />
    </MemoryRouter>,
  )
}

describe('PatientCard', () => {
  it('links the name and View action to the patient detail page, and Edit to the edit page', () => {
    renderCard({ patient: makePatient({ id: 7 }) })

    expect(screen.getByRole('link', { name: 'Jane Doe' })).toHaveAttribute('href', '/patients/7')
    expect(screen.getByRole('link', { name: 'View' })).toHaveAttribute('href', '/patients/7')
    expect(screen.getByRole('link', { name: 'Edit' })).toHaveAttribute('href', '/patients/7/edit')
  })

  it('shows the date of birth, and an MRN only when the patient has one', () => {
    const { rerender } = render(
      <MemoryRouter>
        <PatientCard patient={makePatient({ external_mrn: null })} onArchiveRequest={vi.fn()} />
      </MemoryRouter>,
    )

    expect(screen.getByText(/DOB:/)).toBeInTheDocument()
    expect(screen.queryByText(/MRN:/)).not.toBeInTheDocument()

    rerender(
      <MemoryRouter>
        <PatientCard
          patient={makePatient({ external_mrn: 'MRN-042' })}
          onArchiveRequest={vi.fn()}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText(/MRN: MRN-042/)).toBeInTheDocument()
  })

  it('omits status and updated-at by default', () => {
    renderCard({ patient: makePatient({ status: 'archived', updated_at: '2026-02-01T00:00:00Z' }) })

    expect(screen.queryByText(/Status:/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Updated:/)).not.toBeInTheDocument()
  })

  it('shows status when showStatus is set', () => {
    renderCard({ patient: makePatient({ status: 'archived' }), showStatus: true })

    expect(screen.getByText(/Status: Archived/)).toBeInTheDocument()
  })

  it('shows the updated date when showUpdatedAt is set and the patient has one, but not otherwise', () => {
    const { rerender } = render(
      <MemoryRouter>
        <PatientCard
          patient={makePatient({ updated_at: '2026-02-01T00:00:00Z' })}
          onArchiveRequest={vi.fn()}
          showUpdatedAt
        />
      </MemoryRouter>,
    )
    expect(screen.getByText(/Updated:/)).toBeInTheDocument()

    rerender(
      <MemoryRouter>
        <PatientCard
          patient={makePatient({ updated_at: null })}
          onArchiveRequest={vi.fn()}
          showUpdatedAt
        />
      </MemoryRouter>,
    )
    expect(screen.queryByText(/Updated:/)).not.toBeInTheDocument()
  })

  it('calls onArchiveRequest with the patient when Archive is clicked', async () => {
    const onArchiveRequest = vi.fn()
    const user = userEvent.setup()
    const patient = makePatient()
    renderCard({ patient, onArchiveRequest })

    await user.click(screen.getByRole('button', { name: 'Archive Jane Doe' }))

    expect(onArchiveRequest).toHaveBeenCalledWith(patient)
  })
})
