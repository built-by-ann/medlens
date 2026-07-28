import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MedicationsPage } from '@/pages/MedicationsPage'
import {
  createMedication,
  deleteMedication,
  listMedications,
  updateMedication,
} from '@/api/medications'
import type { Medication } from '@/types/api'

vi.mock('@/api/medications', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/medications')>()

  return {
    ...actual,
    listMedications: vi.fn(),
    createMedication: vi.fn(),
    updateMedication: vi.fn(),
    deleteMedication: vi.fn(),
  }
})

const mockedListMedications = vi.mocked(listMedications)
const mockedCreateMedication = vi.mocked(createMedication)
const mockedUpdateMedication = vi.mocked(updateMedication)
const mockedDeleteMedication = vi.mocked(deleteMedication)

const sampleMedication: Medication = {
  id: 1,
  user_id: 1,
  medication_name: 'Lisinopril',
  dose: '10 mg',
  route: 'oral',
  frequency: 'once daily',
  status: 'active',
  source: 'patient_reported',
  notes: null,
  created_at: '2026-01-01T12:00:00Z',
  updated_at: null,
}

function renderMedicationsPage() {
  return render(
    <MemoryRouter initialEntries={['/medications']}>
      <MedicationsPage />
    </MemoryRouter>,
  )
}

async function fillMedicationForm(
  user: ReturnType<typeof userEvent.setup>,
  container: HTMLElement,
  values: { name: string; dose: string; route: string; frequency: string; status: string },
) {
  await user.type(within(container).getByLabelText('Medication name'), values.name)
  await user.type(within(container).getByLabelText('Dosage'), values.dose)
  await user.type(within(container).getByLabelText('Route'), values.route)
  await user.type(within(container).getByLabelText('Frequency'), values.frequency)
  await user.type(within(container).getByLabelText('Status'), values.status)
}

describe('MedicationsPage', () => {
  beforeEach(() => {
    mockedListMedications.mockReset()
    mockedCreateMedication.mockReset()
    mockedUpdateMedication.mockReset()
    mockedDeleteMedication.mockReset()
  })

  it('shows a loading state while medications are being fetched', () => {
    mockedListMedications.mockReturnValue(new Promise(() => {}))
    renderMedicationsPage()

    expect(screen.getByRole('status')).toHaveTextContent('Loading your medications')
  })

  it('shows the empty state when there are no medications', async () => {
    mockedListMedications.mockResolvedValue([])
    renderMedicationsPage()

    expect(await screen.findByText(/No medications added yet/)).toBeInTheDocument()
  })

  it('renders an existing medication with its key fields', async () => {
    mockedListMedications.mockResolvedValue([sampleMedication])
    renderMedicationsPage()

    expect(await screen.findByRole('heading', { name: 'Lisinopril' })).toBeInTheDocument()
    expect(screen.getByText('10 mg')).toBeInTheDocument()
    expect(screen.getByText('oral')).toBeInTheDocument()
    expect(screen.getByText('once daily')).toBeInTheDocument()
    expect(screen.getByText('active')).toBeInTheDocument()
  })

  it('shows an error state with a retry action when the initial load fails, and recovers on retry', async () => {
    mockedListMedications.mockRejectedValueOnce({
      status: 500,
      message: 'Unable to reach the server.',
    })
    mockedListMedications.mockResolvedValueOnce([sampleMedication])

    const user = userEvent.setup()
    renderMedicationsPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to reach the server.')

    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('heading', { name: 'Lisinopril' })).toBeInTheDocument()
    expect(mockedListMedications).toHaveBeenCalledTimes(2)
  })

  it('validates required fields before submitting a new medication', async () => {
    mockedListMedications.mockResolvedValue([])
    const user = userEvent.setup()
    renderMedicationsPage()

    await screen.findByText(/No medications added yet/)
    await user.click(screen.getByRole('button', { name: 'Add medication' }))

    expect(await screen.findByText('Medication name is required.')).toBeInTheDocument()
    expect(screen.getByText('Dosage is required.')).toBeInTheDocument()
    expect(screen.getByText('Route is required.')).toBeInTheDocument()
    expect(screen.getByText('Frequency is required.')).toBeInTheDocument()
    expect(screen.getByText('Status is required.')).toBeInTheDocument()
    expect(mockedCreateMedication).not.toHaveBeenCalled()
  })

  it('adds a new medication and shows it in the list, clearing the form', async () => {
    mockedListMedications.mockResolvedValue([])
    mockedCreateMedication.mockResolvedValue(sampleMedication)
    const user = userEvent.setup()
    renderMedicationsPage()

    await screen.findByText(/No medications added yet/)
    const form = screen.getByRole('heading', { name: 'Add a medication' }).closest('div')!

    await fillMedicationForm(user, form, {
      name: 'Lisinopril',
      dose: '10 mg',
      route: 'oral',
      frequency: 'once daily',
      status: 'active',
    })
    await user.click(screen.getByRole('button', { name: 'Add medication' }))

    expect(await screen.findByRole('heading', { name: 'Lisinopril' })).toBeInTheDocument()
    expect(mockedCreateMedication).toHaveBeenCalledWith({
      medicationName: 'Lisinopril',
      dose: '10 mg',
      route: 'oral',
      frequency: 'once daily',
      status: 'active',
      notes: '',
    })
    expect(within(form).getByLabelText('Medication name')).toHaveValue('')
  })

  it('shows a server error when adding a medication fails, without clearing the form', async () => {
    mockedListMedications.mockResolvedValue([])
    mockedCreateMedication.mockRejectedValue({ status: 500, message: 'Something went wrong.' })
    const user = userEvent.setup()
    renderMedicationsPage()

    await screen.findByText(/No medications added yet/)
    const form = screen.getByRole('heading', { name: 'Add a medication' }).closest('div')!

    await fillMedicationForm(user, form, {
      name: 'Lisinopril',
      dose: '10 mg',
      route: 'oral',
      frequency: 'once daily',
      status: 'active',
    })
    await user.click(screen.getByRole('button', { name: 'Add medication' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong.')
    expect(within(form).getByLabelText('Medication name')).toHaveValue('Lisinopril')
  })

  it('edits an existing medication and reflects the saved values', async () => {
    mockedListMedications.mockResolvedValue([sampleMedication])
    const updated = { ...sampleMedication, dose: '20 mg' }
    mockedUpdateMedication.mockResolvedValue(updated)
    const user = userEvent.setup()
    renderMedicationsPage()

    await screen.findByRole('heading', { name: 'Lisinopril' })
    await user.click(screen.getByRole('button', { name: 'Edit' }))

    const saveButton = screen.getByRole('button', { name: 'Save' })
    const editForm = saveButton.closest('form')!
    const doseInput = within(editForm).getByLabelText('Dosage')
    await user.clear(doseInput)
    await user.type(doseInput, '20 mg')
    await user.click(saveButton)

    await waitFor(() =>
      expect(mockedUpdateMedication).toHaveBeenCalledWith(1, {
        medicationName: 'Lisinopril',
        dose: '20 mg',
        route: 'oral',
        frequency: 'once daily',
        status: 'active',
        notes: '',
      }),
    )
    expect(await screen.findByText('20 mg')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument()
  })

  it('cancels an edit without saving changes', async () => {
    mockedListMedications.mockResolvedValue([sampleMedication])
    const user = userEvent.setup()
    renderMedicationsPage()

    await screen.findByRole('heading', { name: 'Lisinopril' })
    await user.click(screen.getByRole('button', { name: 'Edit' }))

    const cancelButton = screen.getByRole('button', { name: 'Cancel' })
    const editForm = cancelButton.closest('form')!
    const doseInput = within(editForm).getByLabelText('Dosage')
    await user.clear(doseInput)
    await user.type(doseInput, '999 mg')
    await user.click(cancelButton)

    expect(screen.getByText('10 mg')).toBeInTheDocument()
    expect(mockedUpdateMedication).not.toHaveBeenCalled()
  })

  it('deletes a medication and removes it from the list', async () => {
    mockedListMedications.mockResolvedValue([sampleMedication])
    mockedDeleteMedication.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderMedicationsPage()

    await screen.findByRole('heading', { name: 'Lisinopril' })
    await user.click(screen.getByRole('button', { name: 'Delete Lisinopril' }))

    await waitFor(() => expect(mockedDeleteMedication).toHaveBeenCalledWith(1))
    expect(screen.queryByRole('heading', { name: 'Lisinopril' })).not.toBeInTheDocument()
    expect(await screen.findByText(/No medications added yet/)).toBeInTheDocument()
  })

  it('shows an error and keeps the medication when deleting fails', async () => {
    mockedListMedications.mockResolvedValue([sampleMedication])
    mockedDeleteMedication.mockRejectedValue({ status: 500, message: 'Could not delete.' })
    const user = userEvent.setup()
    renderMedicationsPage()

    await screen.findByRole('heading', { name: 'Lisinopril' })
    await user.click(screen.getByRole('button', { name: 'Delete Lisinopril' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not delete.')
    expect(screen.getByRole('heading', { name: 'Lisinopril' })).toBeInTheDocument()
  })
})
