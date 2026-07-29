import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PatientOverviewPage } from '@/pages/PatientOverviewPage'
import { archivePatient, getPatient } from '@/api/patients'
import { deleteMedication, listMedications, updateMedication } from '@/api/medications'
import type { Medication, Patient } from '@/types/api'

vi.mock('@/api/patients', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/patients')>()

  return {
    ...actual,
    getPatient: vi.fn(),
    archivePatient: vi.fn(),
  }
})

vi.mock('@/api/medications', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/medications')>()

  return {
    ...actual,
    listMedications: vi.fn(),
    updateMedication: vi.fn(),
    deleteMedication: vi.fn(),
  }
})

const mockedGetPatient = vi.mocked(getPatient)
const mockedArchivePatient = vi.mocked(archivePatient)
const mockedListMedications = vi.mocked(listMedications)
const mockedUpdateMedication = vi.mocked(updateMedication)
const mockedDeleteMedication = vi.mocked(deleteMedication)
const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()

  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

const patient: Patient = {
  id: 1,
  user_id: 1,
  first_name: 'Jane',
  last_name: 'Doe',
  date_of_birth: '1980-05-14',
  external_mrn: 'MRN-001',
  status: 'active',
  notes: 'Prefers morning appointments',
  created_at: '2026-01-01T12:00:00Z',
  updated_at: null,
}

const sampleMedication: Medication = {
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
}

function renderOverviewPage() {
  return render(
    <MemoryRouter initialEntries={['/patients/1']}>
      <Routes>
        <Route path="/patients/:patientId" element={<PatientOverviewPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('PatientOverviewPage', () => {
  beforeEach(() => {
    mockedGetPatient.mockReset()
    mockedArchivePatient.mockReset()
    mockedListMedications.mockReset()
    mockedUpdateMedication.mockReset()
    mockedDeleteMedication.mockReset()
    mockNavigate.mockReset()
    mockedListMedications.mockResolvedValue([])
  })

  it('shows a loading state while the patient is being fetched', () => {
    mockedGetPatient.mockReturnValue(new Promise(() => {}))
    renderOverviewPage()

    expect(screen.getByRole('status')).toHaveTextContent('Loading patient')
  })

  it('displays the patient identity, demographic, and notes information', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    renderOverviewPage()

    expect(await screen.findByRole('heading', { name: 'Jane Doe' })).toBeInTheDocument()
    expect(screen.getByText('MRN-001')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Prefers morning appointments')).toBeInTheDocument()
  })

  it('shows a not-found error when the patient does not exist or is not owned by the user', async () => {
    mockedGetPatient.mockRejectedValue({ status: 404, message: 'Patient not found' })
    renderOverviewPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Patient not found')
  })

  it('links the Edit action to the patient edit route', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    renderOverviewPage()

    expect(await screen.findByRole('link', { name: 'Edit' })).toHaveAttribute(
      'href',
      '/patients/1/edit',
    )
  })

  it('shows the empty medications state and a link to add one', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    renderOverviewPage()

    expect(await screen.findByText('No medications recorded yet.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '+ Add medication' })).toHaveAttribute(
      'href',
      '/patients/1/medications',
    )
    expect(mockedListMedications).toHaveBeenCalledWith(1)
  })

  it('shows the patient medication list, reusing the shared medication card', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedListMedications.mockResolvedValue([sampleMedication])
    renderOverviewPage()

    expect(await screen.findByRole('heading', { name: 'Lisinopril' })).toBeInTheDocument()
    expect(screen.getByText('10 mg')).toBeInTheDocument()
  })

  it('shows an error state for the medication list independent of the patient details', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedListMedications.mockRejectedValue({ status: 500, message: 'Could not load medications.' })
    renderOverviewPage()

    await screen.findByRole('heading', { name: 'Jane Doe' })
    expect(await screen.findByText('Could not load medications.')).toBeInTheDocument()
  })

  it('edits a medication directly from the overview page', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedListMedications.mockResolvedValue([sampleMedication])
    mockedUpdateMedication.mockResolvedValue({ ...sampleMedication, dose: '20 mg' })
    const user = userEvent.setup()
    renderOverviewPage()

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
        1,
        5,
        expect.objectContaining({ dose: '20 mg' }),
      ),
    )
  })

  it('deletes a medication directly from the overview page', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedListMedications.mockResolvedValue([sampleMedication])
    mockedDeleteMedication.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderOverviewPage()

    await screen.findByRole('heading', { name: 'Lisinopril' })
    await user.click(screen.getByRole('button', { name: 'Delete Lisinopril' }))

    await waitFor(() => expect(mockedDeleteMedication).toHaveBeenCalledWith(1, 5))
  })

  it('links the Upload documents and View analysis history actions to this patient', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    renderOverviewPage()

    expect(await screen.findByRole('link', { name: 'Upload documents' })).toHaveAttribute(
      'href',
      '/patients/1/upload',
    )
    expect(screen.getByRole('link', { name: 'View analysis history' })).toHaveAttribute(
      'href',
      '/patients/1/analyses',
    )
  })

  it('opens an archive confirmation dialog naming the patient', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    const user = userEvent.setup()
    renderOverviewPage()

    await user.click(await screen.findByRole('button', { name: 'Archive' }))

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Archive Jane Doe?')).toBeInTheDocument()
    expect(mockedArchivePatient).not.toHaveBeenCalled()
  })

  it('cancels an archive without calling the API or navigating', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    const user = userEvent.setup()
    renderOverviewPage()

    await user.click(await screen.findByRole('button', { name: 'Archive' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(mockedArchivePatient).not.toHaveBeenCalled()
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('archives the patient and navigates back to the patients list on success', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedArchivePatient.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderOverviewPage()

    await user.click(await screen.findByRole('button', { name: 'Archive' }))
    await user.click(screen.getByRole('button', { name: 'Archive patient' }))

    await waitFor(() => expect(mockedArchivePatient).toHaveBeenCalledWith(1))
    expect(mockNavigate).toHaveBeenCalledWith('/patients')
  })

  it('shows an error in the dialog and does not navigate when archiving fails', async () => {
    mockedGetPatient.mockResolvedValue(patient)
    mockedArchivePatient.mockRejectedValue({ status: 500, message: 'Could not archive.' })
    const user = userEvent.setup()
    renderOverviewPage()

    await user.click(await screen.findByRole('button', { name: 'Archive' }))
    await user.click(screen.getByRole('button', { name: 'Archive patient' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not archive.')
    expect(mockNavigate).not.toHaveBeenCalled()
  })
})
