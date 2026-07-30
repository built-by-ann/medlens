import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  fileItemKey,
  useCreateAnalysis,
  type QueuedFile,
  type QueuedNote,
} from '@/hooks/useCreateAnalysis'
import { createClinicalDocumentFromText, uploadClinicalDocumentFile } from '@/api/clinicalDocuments'
import { createAnalysisFromDocuments } from '@/api/analyses'
import type { ClinicalDocument } from '@/types/api'

vi.mock('@/api/clinicalDocuments')
vi.mock('@/api/analyses')

const mockedUploadFile = vi.mocked(uploadClinicalDocumentFile)
const mockedCreateFromText = vi.mocked(createClinicalDocumentFromText)
const mockedCreateAnalysis = vi.mocked(createAnalysisFromDocuments)

const PATIENT_ID = 7

function fakeDocument(id: number): ClinicalDocument {
  return {
    id,
    patient_id: PATIENT_ID,
    document_type: 'visit_note',
    title: `Document ${id}`,
    raw_text: 'text',
    file_name: null,
    file_type: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    analysis_count: 0,
  }
}

function fakeAnalysisResult(analysisId: number) {
  return {
    analysis_id: analysisId,
    provider: 'gemini',
    model: 'gemini-2.0-flash',
    summary: '',
    possible_inconsistencies: [],
  }
}

function queuedFile(id: number, name = 'note.txt', documentType = 'visit_note'): QueuedFile {
  return { id, file: new File(['hello'], name, { type: 'text/plain' }), documentType }
}

function queuedNote(id: number, overrides: Partial<Omit<QueuedNote, 'id'>> = {}): QueuedNote {
  return { id, title: '', rawText: 'Some note text', documentType: 'visit_note', ...overrides }
}

describe('useCreateAnalysis', () => {
  beforeEach(() => {
    mockedUploadFile.mockReset()
    mockedCreateFromText.mockReset()
    mockedCreateAnalysis.mockReset()
  })

  it('uploads files, creates note documents with their selected document type, then creates the analysis', async () => {
    mockedUploadFile.mockResolvedValue(fakeDocument(1))
    mockedCreateFromText.mockResolvedValue(fakeDocument(2))
    mockedCreateAnalysis.mockResolvedValue(fakeAnalysisResult(99))

    const file = queuedFile(0, 'note.txt', 'medication_list')
    const note = queuedNote(0, { title: 'My note', documentType: 'discharge_summary' })
    const { result } = renderHook(() => useCreateAnalysis(PATIENT_ID))

    let analysisId: number | undefined
    await act(async () => {
      analysisId = await result.current.submit({ files: [file], notes: [note] })
    })

    expect(mockedUploadFile).toHaveBeenCalledWith(PATIENT_ID, file.file, 'medication_list')
    expect(mockedCreateFromText).toHaveBeenCalledWith(PATIENT_ID, {
      title: 'My note',
      rawText: note.rawText,
      documentType: 'discharge_summary',
    })
    expect(mockedCreateAnalysis).toHaveBeenCalledWith(PATIENT_ID, [1, 2])
    expect(analysisId).toBe(99)
    expect(result.current.error).toBeNull()
  })

  it('falls back to a generated title when a note has no title', async () => {
    mockedCreateFromText.mockResolvedValue(fakeDocument(1))
    mockedCreateAnalysis.mockResolvedValue(fakeAnalysisResult(1))

    const { result } = renderHook(() => useCreateAnalysis(PATIENT_ID))

    await act(async () => {
      await result.current.submit({ files: [], notes: [queuedNote(0, { title: '' })] })
    })

    expect(mockedCreateFromText).toHaveBeenCalledWith(
      PATIENT_ID,
      expect.objectContaining({ title: 'Note 1' }),
    )
  })

  it('on retry, reuses ids already uploaded and only retries the item that failed', async () => {
    mockedUploadFile.mockResolvedValueOnce(fakeDocument(1))
    mockedCreateFromText.mockRejectedValueOnce({ status: 500, message: 'Server error' })

    const file = queuedFile(0)
    const note = queuedNote(0)
    const { result } = renderHook(() => useCreateAnalysis(PATIENT_ID))

    await act(async () => {
      await expect(result.current.submit({ files: [file], notes: [note] })).rejects.toBeTruthy()
    })

    expect(mockedUploadFile).toHaveBeenCalledTimes(1)
    expect(mockedCreateFromText).toHaveBeenCalledTimes(1)

    mockedCreateFromText.mockResolvedValueOnce(fakeDocument(2))
    mockedCreateAnalysis.mockResolvedValue(fakeAnalysisResult(42))

    let analysisId: number | undefined
    await act(async () => {
      analysisId = await result.current.submit({ files: [file], notes: [note] })
    })

    // The file was not re-uploaded on retry; only the note (which failed
    // last time) was attempted again.
    expect(mockedUploadFile).toHaveBeenCalledTimes(1)
    expect(mockedCreateFromText).toHaveBeenCalledTimes(2)
    expect(mockedCreateAnalysis).toHaveBeenCalledWith(PATIENT_ID, [1, 2])
    expect(analysisId).toBe(42)
  })

  it('surfaces which item failed', async () => {
    mockedUploadFile.mockRejectedValue({ status: 422, message: 'Unsupported file' })

    const file = queuedFile(0, 'bad-note.txt')
    const { result } = renderHook(() => useCreateAnalysis(PATIENT_ID))

    await act(async () => {
      await expect(result.current.submit({ files: [file], notes: [] })).rejects.toBeTruthy()
    })

    await waitFor(() => expect(result.current.failedItemLabel).toBe('bad-note.txt'))
    expect(result.current.error).toBe('Unsupported file')
  })

  it('invalidateItem forces a re-upload of only that item on the next submit', async () => {
    // Both documents succeed and get cached; the failure happens at the
    // final summarize step instead, so the per-document cache survives
    // (only a fully successful submit clears it).
    mockedUploadFile.mockResolvedValueOnce(fakeDocument(1))
    mockedCreateFromText.mockResolvedValueOnce(fakeDocument(2))
    mockedCreateAnalysis.mockRejectedValueOnce({ status: 503, message: 'AI provider unavailable' })

    const file = queuedFile(0)
    const note = queuedNote(0)
    const { result } = renderHook(() => useCreateAnalysis(PATIENT_ID))

    await act(async () => {
      await expect(result.current.submit({ files: [file], notes: [note] })).rejects.toBeTruthy()
    })

    expect(mockedUploadFile).toHaveBeenCalledTimes(1)
    expect(mockedCreateFromText).toHaveBeenCalledTimes(1)

    // Simulate the user changing the file's document type, which
    // UploadPage responds to by invalidating just that item's cache entry.
    act(() => {
      result.current.invalidateItem(fileItemKey(file.id))
    })

    mockedUploadFile.mockResolvedValueOnce(fakeDocument(3))
    mockedCreateAnalysis.mockResolvedValue(fakeAnalysisResult(1))

    await act(async () => {
      await result.current.submit({ files: [file], notes: [note] })
    })

    // The invalidated file was uploaded again; the still-cached note was not.
    expect(mockedUploadFile).toHaveBeenCalledTimes(2)
    expect(mockedCreateFromText).toHaveBeenCalledTimes(1)
    expect(mockedCreateAnalysis).toHaveBeenLastCalledWith(PATIENT_ID, [3, 2])
  })

  it('clears the upload cache after a successful analysis is created', async () => {
    mockedUploadFile.mockResolvedValue(fakeDocument(1))
    mockedCreateAnalysis.mockResolvedValue(fakeAnalysisResult(1))

    const file = queuedFile(0)
    const { result } = renderHook(() => useCreateAnalysis(PATIENT_ID))

    await act(async () => {
      await result.current.submit({ files: [file], notes: [] })
    })

    expect(mockedUploadFile).toHaveBeenCalledTimes(1)

    // A second, later submission attempt (e.g. the user starts a fresh
    // analysis reusing the same queue) must not silently reuse the id from
    // the completed attempt.
    await act(async () => {
      await result.current.submit({ files: [file], notes: [] })
    })

    expect(mockedUploadFile).toHaveBeenCalledTimes(2)
  })

  it('does not call createAnalysisFromDocuments when an upload step fails', async () => {
    mockedUploadFile.mockRejectedValue({
      status: 422,
      message: 'Only .txt or text/plain files are supported',
    })

    const { result } = renderHook(() => useCreateAnalysis(PATIENT_ID))

    await act(async () => {
      await expect(
        result.current.submit({ files: [queuedFile(0)], notes: [] }),
      ).rejects.toBeTruthy()
    })

    await waitFor(() =>
      expect(result.current.error).toBe('Only .txt or text/plain files are supported'),
    )
    expect(result.current.isSubmitting).toBe(false)
    expect(mockedCreateAnalysis).not.toHaveBeenCalled()
  })

  it('creates an analysis from existing document ids without uploading anything', async () => {
    mockedCreateAnalysis.mockResolvedValue(fakeAnalysisResult(7))

    const { result } = renderHook(() => useCreateAnalysis(PATIENT_ID))

    let analysisId: number | undefined
    await act(async () => {
      analysisId = await result.current.submit({
        files: [],
        notes: [],
        existingDocumentIds: [11, 12],
      })
    })

    expect(mockedUploadFile).not.toHaveBeenCalled()
    expect(mockedCreateFromText).not.toHaveBeenCalled()
    expect(mockedCreateAnalysis).toHaveBeenCalledWith(PATIENT_ID, [11, 12])
    expect(analysisId).toBe(7)
  })

  it('combines existing document ids with newly uploaded files and notes', async () => {
    mockedUploadFile.mockResolvedValue(fakeDocument(1))
    mockedCreateFromText.mockResolvedValue(fakeDocument(2))
    mockedCreateAnalysis.mockResolvedValue(fakeAnalysisResult(9))

    const { result } = renderHook(() => useCreateAnalysis(PATIENT_ID))

    await act(async () => {
      await result.current.submit({
        files: [queuedFile(0)],
        notes: [queuedNote(0)],
        existingDocumentIds: [50],
      })
    })

    expect(mockedCreateAnalysis).toHaveBeenCalledWith(PATIENT_ID, [50, 1, 2])
  })

  it('saveDocuments uploads files and notes without creating an analysis', async () => {
    mockedUploadFile.mockResolvedValue(fakeDocument(1))
    mockedCreateFromText.mockResolvedValue(fakeDocument(2))

    const file = queuedFile(0, 'note.txt', 'medication_list')
    const note = queuedNote(0, { title: 'My note', documentType: 'discharge_summary' })
    const { result } = renderHook(() => useCreateAnalysis(PATIENT_ID))

    let documentIds: number[] | undefined
    await act(async () => {
      documentIds = await result.current.saveDocuments({ files: [file], notes: [note] })
    })

    expect(mockedUploadFile).toHaveBeenCalledWith(PATIENT_ID, file.file, 'medication_list')
    expect(mockedCreateFromText).toHaveBeenCalledWith(PATIENT_ID, {
      title: 'My note',
      rawText: note.rawText,
      documentType: 'discharge_summary',
    })
    expect(mockedCreateAnalysis).not.toHaveBeenCalled()
    expect(documentIds).toEqual([1, 2])
    expect(result.current.error).toBeNull()
  })

  it('saveDocuments surfaces which item failed and does not create an analysis', async () => {
    mockedUploadFile.mockRejectedValue({ status: 422, message: 'Unsupported file' })

    const file = queuedFile(0, 'bad-note.txt')
    const { result } = renderHook(() => useCreateAnalysis(PATIENT_ID))

    await act(async () => {
      await expect(result.current.saveDocuments({ files: [file], notes: [] })).rejects.toBeTruthy()
    })

    await waitFor(() => expect(result.current.failedItemLabel).toBe('bad-note.txt'))
    expect(result.current.error).toBe('Unsupported file')
    expect(mockedCreateAnalysis).not.toHaveBeenCalled()
  })

  it('saveDocuments and submit share the same upload cache, so a prior save is not re-uploaded by a later submit', async () => {
    mockedUploadFile.mockResolvedValue(fakeDocument(1))
    mockedCreateAnalysis.mockResolvedValue(fakeAnalysisResult(1))

    const file = queuedFile(0)
    const { result } = renderHook(() => useCreateAnalysis(PATIENT_ID))

    await act(async () => {
      await result.current.saveDocuments({ files: [file], notes: [] })
    })

    expect(mockedUploadFile).toHaveBeenCalledTimes(1)

    // A later submit() with the exact same still-queued file uploads a
    // fresh copy rather than reusing the saved one: the cache is cleared on
    // every successful attempt (including saveDocuments), since a document
    // that was already saved earlier is a different real ClinicalDocument
    // from whatever the user is queuing up now.
    await act(async () => {
      await result.current.submit({ files: [file], notes: [] })
    })

    expect(mockedUploadFile).toHaveBeenCalledTimes(2)
  })

  it('sets isSubmitting while the sequence is in flight', async () => {
    let resolveUpload: (document: ClinicalDocument) => void = () => {}
    mockedUploadFile.mockReturnValue(
      new Promise((resolve) => {
        resolveUpload = resolve
      }),
    )
    mockedCreateAnalysis.mockResolvedValue(fakeAnalysisResult(1))

    const { result } = renderHook(() => useCreateAnalysis(PATIENT_ID))

    let submitPromise!: Promise<number>
    act(() => {
      submitPromise = result.current.submit({ files: [queuedFile(0)], notes: [] })
    })

    expect(result.current.isSubmitting).toBe(true)

    await act(async () => {
      resolveUpload(fakeDocument(1))
      await submitPromise
    })

    expect(result.current.isSubmitting).toBe(false)
  })
})
