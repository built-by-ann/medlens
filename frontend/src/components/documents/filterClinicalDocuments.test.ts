import { describe, expect, it } from 'vitest'
import { filterClinicalDocuments } from '@/components/documents/filterClinicalDocuments'
import type { ClinicalDocument } from '@/types/api'

function makeDocument(overrides: Partial<ClinicalDocument>): ClinicalDocument {
  return {
    id: 1,
    patient_id: 7,
    document_type: 'visit_note',
    title: 'March Visit Note',
    raw_text: 'text',
    file_name: null,
    file_type: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    analysis_count: 0,
    ...overrides,
  }
}

describe('filterClinicalDocuments', () => {
  const documents = [
    makeDocument({ id: 1, title: 'March Visit Note', document_type: 'visit_note' }),
    makeDocument({ id: 2, title: 'Discharge Summary', document_type: 'discharge_summary' }),
  ]

  it('returns every document when the search term is empty', () => {
    expect(filterClinicalDocuments(documents, '')).toEqual(documents)
  })

  it('returns every document when the search term is only whitespace', () => {
    expect(filterClinicalDocuments(documents, '   ')).toEqual(documents)
  })

  it('matches by title, case-insensitively', () => {
    expect(filterClinicalDocuments(documents, 'march')).toEqual([documents[0]])
  })

  it('matches by document type label, case-insensitively', () => {
    expect(filterClinicalDocuments(documents, 'discharge summary')).toEqual([documents[1]])
  })

  it('returns an empty array when nothing matches', () => {
    expect(filterClinicalDocuments(documents, 'nonexistent')).toEqual([])
  })

  it('does not mutate the input array', () => {
    const original = [...documents]
    filterClinicalDocuments(documents, 'march')
    expect(documents).toEqual(original)
  })
})
