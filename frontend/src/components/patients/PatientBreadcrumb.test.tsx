import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { PatientBreadcrumb } from '@/components/patients/PatientBreadcrumb'
import type { Patient } from '@/types/api'

const patient: Patient = {
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
}

function renderBreadcrumb(trail?: { label: string; to?: string }[]) {
  return render(
    <MemoryRouter>
      <PatientBreadcrumb patient={patient} trail={trail} />
    </MemoryRouter>,
  )
}

describe('PatientBreadcrumb', () => {
  it('links back to Patients and always names the trail region "Breadcrumb"', () => {
    renderBreadcrumb()

    const nav = screen.getByRole('navigation', { name: 'Breadcrumb' })
    expect(within(nav).getByRole('link', { name: 'Patients' })).toHaveAttribute('href', '/patients')
  })

  it('makes the patient the current (final) crumb when there is no further trail, not a link', () => {
    renderBreadcrumb()

    const patientCrumb = screen.getByText('Jane Doe')
    expect(patientCrumb.tagName).not.toBe('A')
    expect(patientCrumb).toHaveAttribute('aria-current', 'page')
  })

  it('links the patient name to their detail page when it is not the final crumb', () => {
    renderBreadcrumb([{ label: 'Analyses', to: '/patients/7/analyses' }])

    expect(screen.getByRole('link', { name: 'Jane Doe' })).toHaveAttribute('href', '/patients/7')
  })

  it('renders extra trail items with a destination as links, except the final one', () => {
    renderBreadcrumb([{ label: 'Analyses', to: '/patients/7/analyses' }, { label: 'Analysis #5' }])

    const analysesCrumb = screen.getByRole('link', { name: 'Analyses' })
    expect(analysesCrumb).toHaveAttribute('href', '/patients/7/analyses')

    const currentCrumb = screen.getByText('Analysis #5')
    expect(currentCrumb.tagName).not.toBe('A')
    expect(currentCrumb).toHaveAttribute('aria-current', 'page')
  })

  it('renders a trail item with no destination as plain text even when it is not the final crumb', () => {
    renderBreadcrumb([{ label: 'Untitled step' }, { label: 'Current step' }])

    const middleCrumb = screen.getByText('Untitled step')
    expect(middleCrumb.tagName).not.toBe('A')
    expect(middleCrumb).not.toHaveAttribute('aria-current')
  })

  it('separates every crumb with a decorative slash hidden from assistive tech', () => {
    renderBreadcrumb([{ label: 'Analyses', to: '/patients/7/analyses' }])

    // Patients / Jane Doe / Analyses: 3 crumbs, 2 separators.
    const separators = screen.getAllByText('/')
    expect(separators).toHaveLength(2)
    separators.forEach((separator) => expect(separator).toHaveAttribute('aria-hidden', 'true'))
  })
})
