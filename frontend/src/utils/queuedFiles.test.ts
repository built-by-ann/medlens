import { describe, expect, it } from 'vitest'
import { findDuplicateExistingTitle, isDuplicateFile } from '@/utils/queuedFiles'
import type { QueuedFile } from '@/hooks/useCreateAnalysis'

function makeFile(name = 'note.txt', size = 5): File {
  return new File([new Uint8Array(size)], name, { type: 'text/plain' })
}

describe('isDuplicateFile', () => {
  it('matches an already-queued file by name and size', () => {
    const queued: QueuedFile[] = [
      { id: 0, file: makeFile('note.txt', 5), documentType: 'visit_note' },
    ]

    expect(isDuplicateFile(queued, makeFile('note.txt', 5))).toBe(true)
  })

  it('does not match when the size differs', () => {
    const queued: QueuedFile[] = [
      { id: 0, file: makeFile('note.txt', 5), documentType: 'visit_note' },
    ]

    expect(isDuplicateFile(queued, makeFile('note.txt', 9))).toBe(false)
  })
})

describe('findDuplicateExistingTitle', () => {
  it('matches a file whose derived title equals an existing document title', () => {
    const match = findDuplicateExistingTitle({ file: makeFile('March Visit Note.txt') }, [
      'Discharge Summary',
      'March Visit Note',
    ])

    expect(match).toBe('March Visit Note')
  })

  it('matches case-insensitively and ignores surrounding whitespace', () => {
    const match = findDuplicateExistingTitle({ file: makeFile('march visit note.txt') }, [
      '  March Visit Note  ',
    ])

    expect(match).toBe('  March Visit Note  ')
  })

  it('returns undefined when no existing title matches', () => {
    const match = findDuplicateExistingTitle({ file: makeFile('New Note.txt') }, [
      'March Visit Note',
    ])

    expect(match).toBeUndefined()
  })

  it('returns undefined when there are no existing documents', () => {
    expect(
      findDuplicateExistingTitle({ file: makeFile('March Visit Note.txt') }, []),
    ).toBeUndefined()
  })

  it('matches against a provider-edited title rather than the original filename', () => {
    const match = findDuplicateExistingTitle(
      { file: makeFile('scan1.txt'), title: 'March Visit Note' },
      ['March Visit Note'],
    )

    expect(match).toBe('March Visit Note')
  })

  it('falls back to the filename-derived title when the edited title is blank', () => {
    const match = findDuplicateExistingTitle(
      { file: makeFile('March Visit Note.txt'), title: '   ' },
      ['March Visit Note'],
    )

    expect(match).toBe('March Visit Note')
  })
})
