import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useDocumentQueue } from '@/hooks/useDocumentQueue'

function makeFile(name = 'note.txt', size = 5, type = 'text/plain'): File {
  return new File([new Uint8Array(size)], name, { type })
}

describe('useDocumentQueue', () => {
  it('starts empty', () => {
    const { result } = renderHook(() => useDocumentQueue())

    expect(result.current.files).toEqual([])
    expect(result.current.notes).toEqual([])
    expect(result.current.totalCount).toBe(0)
    expect(result.current.fileError).toBeNull()
  })

  it('queues a supported file with the default document type', () => {
    const { result } = renderHook(() => useDocumentQueue())

    act(() => {
      result.current.handleFilesSelected([makeFile('note.txt')])
    })

    expect(result.current.files).toHaveLength(1)
    expect(result.current.files[0]).toMatchObject({ documentType: 'visit_note' })
    expect(result.current.totalCount).toBe(1)
    expect(result.current.fileError).toBeNull()
  })

  it('queues a supported .csv file, defaulting its document type to Medication list', () => {
    const { result } = renderHook(() => useDocumentQueue())

    act(() => {
      result.current.handleFilesSelected([makeFile('medications.csv', 5, 'text/csv')])
    })

    expect(result.current.files).toHaveLength(1)
    expect(result.current.files[0]).toMatchObject({ documentType: 'medication_list' })
    expect(result.current.fileError).toBeNull()
  })

  it('rejects an unsupported file type and does not queue it', () => {
    const { result } = renderHook(() => useDocumentQueue())

    act(() => {
      result.current.handleFilesSelected([makeFile('note.exe', 5, 'application/octet-stream')])
    })

    expect(result.current.files).toEqual([])
    expect(result.current.fileError).toContain('not a supported file type')
  })

  it('does not queue the same file twice', () => {
    const { result } = renderHook(() => useDocumentQueue())
    const file = makeFile('note.txt')

    act(() => {
      result.current.handleFilesSelected([file])
    })
    act(() => {
      result.current.handleFilesSelected([file])
    })

    expect(result.current.files).toHaveLength(1)
  })

  it('removes a queued file', () => {
    const { result } = renderHook(() => useDocumentQueue())

    act(() => {
      result.current.handleFilesSelected([makeFile('note.txt')])
    })
    const id = result.current.files[0]!.id

    act(() => {
      result.current.handleRemoveFile(id)
    })

    expect(result.current.files).toEqual([])
  })

  it('changes a queued file’s document type', () => {
    const { result } = renderHook(() => useDocumentQueue())

    act(() => {
      result.current.handleFilesSelected([makeFile('note.txt')])
    })
    const id = result.current.files[0]!.id

    act(() => {
      result.current.handleFileDocumentTypeChange(id, 'discharge_summary')
    })

    expect(result.current.files[0]!.documentType).toBe('discharge_summary')
  })

  it('adds, updates, and removes a manually entered note', () => {
    const { result } = renderHook(() => useDocumentQueue())

    act(() => {
      result.current.handleAddNote({
        title: 'My note',
        rawText: 'Some text',
        documentType: 'visit_note',
      })
    })

    expect(result.current.notes).toHaveLength(1)
    expect(result.current.totalCount).toBe(1)
    const id = result.current.notes[0]!.id

    act(() => {
      result.current.handleUpdateNote(id, {
        title: 'Updated title',
        rawText: 'Updated text',
        documentType: 'discharge_summary',
      })
    })

    expect(result.current.notes[0]).toMatchObject({
      title: 'Updated title',
      rawText: 'Updated text',
      documentType: 'discharge_summary',
    })

    act(() => {
      result.current.handleRemoveNote(id)
    })

    expect(result.current.notes).toEqual([])
    expect(result.current.totalCount).toBe(0)
  })

  it('counts files and notes together in totalCount', () => {
    const { result } = renderHook(() => useDocumentQueue())

    act(() => {
      result.current.handleFilesSelected([makeFile('a.txt')])
      result.current.handleAddNote({ title: '', rawText: 'text', documentType: 'visit_note' })
    })

    expect(result.current.totalCount).toBe(2)
  })
})
