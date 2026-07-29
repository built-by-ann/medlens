import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PatientMedicationsPage } from '@/pages/PatientMedicationsPage'
import { getPatient } from '@/api/patients'
import {
  createMedication,
  deleteMedication,
  importMedicationsCsv,
  listMedications,
  updateMedication,
} from '@/api/medications'
import type { Medication, Patient } from '@/types/api'

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    getPatient: vi.fn(),
  }
})

vi.mock('@/api/medications', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/medications')>()

  return {
    ...actual,
    listMedications: vi.fn(),
    createMedication: vi.fn(),
    updateMedication: vi.fn(),
    deleteMedication: vi.fn(),
    importMedicationsCsv: vi.fn(),
  }
})

const mockedGetPatient = vi.mocked(getPatient)
const mockedListMedications = vi.mocked(listMedications)
const mockedCreateMedication = vi.mocked(createMedication)
const mockedUpdateMedication = vi.mocked(updateMedication)
const mockedDeleteMedication = vi.mocked(deleteMedication)
const mockedImportMedicationsCsv = vi.mocked(importMedicationsCsv)

const patient: Patient = {
  id: 42,
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

const sampleMedication: Medication = {
  id: 1,
  patient_id: 42,
  medication_name: 'Lisinopril',
  dose: '10 mg',
  route: 'oral',
  frequency: 'once daily',
  status: 'active',
  source: 'patient_reported',
  notes: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/patients/42/medications']}>
      <Routes>
        <Route path="/patients/:patientId/medications" element={<PatientMedicationsPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('PatientMedicationsPage', () => {
  beforeEach(() => {
    mockedGetPatient.mockReset()
    mockedListMedications.mockReset()
    mockedCreateMedication.mockReset()
    mockedUpdateMedication.mockReset()
    mockedDeleteMedication.mockReset()
    mockedImportMedicationsCsv.mockReset()
    mockedGetPatient.mockResolvedValue(patient)
    mockedListMedications.mockResolvedValue([])
  })

  it('shows a loading state while the patient is being fetched', () => {
    mockedGetPatient.mockReturnValue(new Promise(() => {}))
    renderPage()

    expect(screen.getByRole('status')).toHaveTextContent('Loading patient')
  })

  it('shows the patient name in the page title and a back link to their overview', async () => {
    mockedListMedications.mockResolvedValue([])
    renderPage()

    expect(
      await screen.findByRole('heading', { name: /Medications for Jane Doe/ }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Back to Jane Doe/ })).toHaveAttribute(
      'href',
      '/patients/42',
    )
  })

  it('shows an error state when the patient fails to load', async () => {
    mockedGetPatient.mockReset()
    mockedGetPatient.mockRejectedValue({ status: 404, message: 'Patient not found' })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Patient not found')
  })

  it('shows the empty state when there are no medications', async () => {
    mockedListMedications.mockResolvedValue([])
    renderPage()

    expect(await screen.findByText(/No medications added yet/)).toBeInTheDocument()
    expect(mockedListMedications).toHaveBeenCalledWith(42)
  })

  it('renders an existing medication with its key fields', async () => {
    mockedListMedications.mockResolvedValue([sampleMedication])
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Lisinopril' })).toBeInTheDocument()
    expect(screen.getByText('10 mg')).toBeInTheDocument()
  })

  it('shows an error state for the medication list, with a working retry', async () => {
    mockedListMedications.mockRejectedValueOnce({
      status: 500,
      message: 'Unable to reach the server.',
    })
    mockedListMedications.mockResolvedValueOnce([sampleMedication])
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText('Unable to reach the server.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('heading', { name: 'Lisinopril' })).toBeInTheDocument()
  })

  it('adds a new medication scoped to the current patient', async () => {
    mockedListMedications.mockResolvedValue([])
    mockedCreateMedication.mockResolvedValue(sampleMedication)
    const user = userEvent.setup()
    renderPage()

    await screen.findByText(/No medications added yet/)
    const form = screen.getByRole('heading', { name: 'Add a medication' }).closest('div')!

    await user.type(within(form).getByLabelText('Medication name'), 'Lisinopril')
    await user.type(within(form).getByLabelText('Dosage'), '10 mg')
    await user.type(within(form).getByLabelText('Route'), 'oral')
    await user.type(within(form).getByLabelText('Frequency'), 'once daily')
    await user.type(within(form).getByLabelText('Status'), 'active')
    await user.click(screen.getByRole('button', { name: 'Add medication' }))

    await waitFor(() =>
      expect(mockedCreateMedication).toHaveBeenCalledWith(42, {
        medicationName: 'Lisinopril',
        dose: '10 mg',
        route: 'oral',
        frequency: 'once daily',
        status: 'active',
        notes: '',
      }),
    )
    expect(await screen.findByRole('heading', { name: 'Lisinopril' })).toBeInTheDocument()
  })

  it('edits an existing medication', async () => {
    mockedListMedications.mockResolvedValue([sampleMedication])
    mockedUpdateMedication.mockResolvedValue({ ...sampleMedication, dose: '20 mg' })
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Lisinopril' })
    await user.click(screen.getByRole('button', { name: 'Edit' }))

    const saveButton = screen.getByRole('button', { name: 'Save' })
    const editForm = saveButton.closest('form')!
    const doseInput = within(editForm).getByLabelText('Dosage')
    await user.clear(doseInput)
    await user.type(doseInput, '20 mg')
    await user.click(saveButton)

    await waitFor(() =>
      expect(mockedUpdateMedication).toHaveBeenCalledWith(
        42,
        1,
        expect.objectContaining({ dose: '20 mg' }),
      ),
    )
    expect(await screen.findByText('20 mg')).toBeInTheDocument()
  })

  it('deletes a medication and removes it from the list', async () => {
    mockedListMedications.mockResolvedValue([sampleMedication])
    mockedDeleteMedication.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Lisinopril' })
    await user.click(screen.getByRole('button', { name: 'Delete Lisinopril' }))

    await waitFor(() => expect(mockedDeleteMedication).toHaveBeenCalledWith(42, 1))
    expect(screen.queryByRole('heading', { name: 'Lisinopril' })).not.toBeInTheDocument()
  })

  it('shows the CSV import section within the patient-scoped medications page', async () => {
    mockedListMedications.mockResolvedValue([])
    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'Import medications from CSV' }),
    ).toBeInTheDocument()
  })

  it('imports a CSV file scoped to the current patient and refreshes the list', async () => {
    mockedListMedications.mockResolvedValueOnce([])
    mockedListMedications.mockResolvedValueOnce([sampleMedication])
    mockedImportMedicationsCsv.mockResolvedValue({
      rows_processed: 1,
      medications_created: 1,
      blank_rows_ignored: 0,
    })
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('heading', { name: 'Import medications from CSV' })
    const file = new File(['medication_name,dose\nLisinopril,10 mg\n'], 'meds.csv', {
      type: 'text/csv',
    })
    await user.upload(screen.getByTestId('csv-file-input'), file)
    await user.click(screen.getByRole('button', { name: 'Import CSV' }))

    await waitFor(() => expect(mockedImportMedicationsCsv).toHaveBeenCalledWith(42, file))
    expect(await screen.findByRole('heading', { name: 'Lisinopril' })).toBeInTheDocument()
  })
})
