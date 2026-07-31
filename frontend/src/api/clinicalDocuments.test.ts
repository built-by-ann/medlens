import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '@/api/client'
import { isCsv, isSupportedFileType, uploadClinicalDocumentFile } from '@/api/clinicalDocuments'
import type { ClinicalDocument } from '@/types/api'

vi.mock('@/api/client', () => ({
  apiClient: { post: vi.fn() },
}))

const mockedPost = vi.mocked(apiClient.post)

function fakeDocument(): ClinicalDocument {
  return {
    id: 1,
    patient_id: 7,
    document_type: 'medication_list',
    title: 'Uploaded Medication CSV',
    raw_text: 'medication_name,dose\nLisinopril,10mg',
    file_name: 'medications.csv',
    file_type: 'csv',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    analysis_count: 0,
  }
}

describe('isCsv', () => {
  it('is true for a .csv file regardless of content type', () => {
    expect(isCsv(new File(['a'], 'medications.csv', { type: '' }))).toBe(true)
  })

  it('is true for a text/csv content type regardless of extension', () => {
    expect(isCsv(new File(['a'], 'export', { type: 'text/csv' }))).toBe(true)
  })

  it('is false for a .txt file', () => {
    expect(isCsv(new File(['a'], 'note.txt', { type: 'text/plain' }))).toBe(false)
  })
})

describe('isSupportedFileType', () => {
  it('accepts a .csv file', () => {
    expect(isSupportedFileType(new File(['a'], 'medications.csv', { type: 'text/csv' }))).toBe(true)
  })
})

describe('uploadClinicalDocumentFile', () => {
  beforeEach(() => {
    mockedPost.mockReset()
  })

  it('routes a .csv file to upload-csv, never to the medication import endpoint', async () => {
    mockedPost.mockResolvedValue({ data: fakeDocument() })
    const file = new File(['medication_name,dose\nLisinopril,10mg'], 'medications.csv', {
      type: 'text/csv',
    })

    await uploadClinicalDocumentFile(7, file, 'medication_list')

    expect(mockedPost).toHaveBeenCalledTimes(1)
    const [endpoint] = mockedPost.mock.calls[0]!
    expect(endpoint).toBe('/patients/7/clinical-documents/upload-csv')
  })

  it('still routes a .pdf file to upload-pdf, unaffected by CSV support', async () => {
    mockedPost.mockResolvedValue({ data: fakeDocument() })
    const file = new File(['%PDF-1.4'], 'note.pdf', { type: 'application/pdf' })

    await uploadClinicalDocumentFile(7, file, 'visit_note')

    const [endpoint] = mockedPost.mock.calls[0]!
    expect(endpoint).toBe('/patients/7/clinical-documents/upload-pdf')
  })

  it('still routes a .txt file to upload-txt, unaffected by CSV support', async () => {
    mockedPost.mockResolvedValue({ data: fakeDocument() })
    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })

    await uploadClinicalDocumentFile(7, file, 'visit_note')

    const [endpoint] = mockedPost.mock.calls[0]!
    expect(endpoint).toBe('/patients/7/clinical-documents/upload-txt')
  })
})
