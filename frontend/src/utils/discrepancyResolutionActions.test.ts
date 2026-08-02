import { describe, expect, it } from 'vitest'
import {
  buildResolutionPayload,
  getDiscrepancyActions,
  requiredFieldKeys,
} from '@/utils/discrepancyResolutionActions'
import type { MedicationDiscrepancy } from '@/types/api'

function makeDiscrepancy(overrides: Partial<MedicationDiscrepancy> = {}): MedicationDiscrepancy {
  return {
    id: 1,
    analysis_id: 7,
    medication_id: null,
    medication_mention_id: null,
    discrepancy_type: 'missing_from_medication_list',
    severity: 'high',
    title: 'Lisinopril not found in medication list',
    ai_explanation: null,
    recommendation: null,
    expected_value: null,
    observed_value: null,
    resolution_status: 'open',
    resolution_action: null,
    resolved_at: null,
    resolution_note: null,
    resolved_by: null,
    created_at: '2026-01-01T12:00:00Z',
    updated_at: null,
    medication: null,
    medication_mention: null,
    ...overrides,
  }
}

const mention = {
  id: 9,
  medication_name: 'Lisinopril',
  dose: '10 mg',
  route: 'oral',
  frequency: 'once daily',
  status: 'active',
  context_text: null,
  clinical_document: { id: 1, title: 'Visit Note', document_type: 'visit_note' },
}

const medication = {
  id: 55,
  patient_id: 42,
  medication_name: 'Lisinopril',
  dose: '20 mg',
  route: 'oral',
  frequency: 'once daily',
  status: 'active',
  source: 'patient_reported',
  notes: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: null,
}

describe('getDiscrepancyActions', () => {
  it('offers Add Medication and Dismiss for a missing medication, in that order', () => {
    const discrepancy = makeDiscrepancy({
      discrepancy_type: 'missing_from_medication_list',
      medication_mention: mention,
    })

    const actions = getDiscrepancyActions(discrepancy)

    expect(actions.map((action) => action.label)).toEqual(['Add Medication', 'Dismiss'])
  })

  it("Add Medication's fields are pre-filled from the mention", () => {
    const discrepancy = makeDiscrepancy({
      discrepancy_type: 'missing_from_medication_list',
      medication_mention: mention,
    })

    const addAction = getDiscrepancyActions(discrepancy)[0]!
    const fieldsByKey = Object.fromEntries(addAction.fields.map((f) => [f.key, f.value]))

    expect(addAction.editable).toBe(true)
    expect(fieldsByKey).toEqual({
      medication_name: 'Lisinopril',
      dose: '10 mg',
      route: 'oral',
      frequency: 'once daily',
      status: 'active',
    })
  })

  it('never offers update_medication or mark-status actions for a missing medication', () => {
    const discrepancy = makeDiscrepancy({ discrepancy_type: 'missing_from_medication_list' })

    const labels = getDiscrepancyActions(discrepancy).map((action) => action.label)

    expect(labels).not.toContain('Update Medication')
    expect(labels).not.toContain('Edit Manually')
    expect(labels).not.toContain('Mark Discontinued')
  })

  it('offers Update Medication, Edit Manually, and Dismiss for a dose conflict with a suggested value', () => {
    const discrepancy = makeDiscrepancy({
      discrepancy_type: 'dose_conflict',
      medication,
      medication_mention: mention,
    })

    const actions = getDiscrepancyActions(discrepancy)

    expect(actions.map((action) => action.label)).toEqual([
      'Update Medication',
      'Edit Manually',
      'Dismiss',
    ])
    expect(actions[0]!.fields).toEqual([{ key: 'dose', label: 'Dose', value: '10 mg' }])
    expect(actions[0]!.editable).toBe(false)
    expect(actions[0]!.description).toContain('10 mg')
  })

  it('omits Update Medication when the mention never reported that field', () => {
    const discrepancy = makeDiscrepancy({
      discrepancy_type: 'dose_conflict',
      medication,
      medication_mention: { ...mention, dose: null },
    })

    const labels = getDiscrepancyActions(discrepancy).map((action) => action.label)

    expect(labels).toEqual(['Edit Manually', 'Dismiss'])
  })

  it("Edit Manually's fields are pre-filled from the current medication, not the mention", () => {
    const discrepancy = makeDiscrepancy({
      discrepancy_type: 'dose_conflict',
      medication,
      medication_mention: mention,
    })

    const editAction = getDiscrepancyActions(discrepancy).find((a) => a.key === 'edit')!
    const fieldsByKey = Object.fromEntries(editAction.fields.map((f) => [f.key, f.value]))

    expect(fieldsByKey.dose).toBe('20 mg') // the medication's value, not the mention's 10 mg
    expect(editAction.editable).toBe(true)
  })

  it('offers the right field for each of dose/route/frequency conflicts', () => {
    for (const [type, key, label] of [
      ['dose_conflict', 'dose', 'Dose'],
      ['route_conflict', 'route', 'Route'],
      ['frequency_conflict', 'frequency', 'Frequency'],
    ] as const) {
      const discrepancy = makeDiscrepancy({
        discrepancy_type: type,
        medication,
        medication_mention: mention,
      })

      const updateAction = getDiscrepancyActions(discrepancy)[0]!
      expect(updateAction.fields).toEqual([{ key, label, value: mention[key] }])
    }
  })

  it('offers Mark Discontinued, Mark Active, Edit Manually, and Dismiss for a status conflict', () => {
    const discrepancy = makeDiscrepancy({
      discrepancy_type: 'discontinued_status_conflict',
      medication,
    })

    const actions = getDiscrepancyActions(discrepancy)

    expect(actions.map((action) => action.label)).toEqual([
      'Mark Discontinued',
      'Mark Active',
      'Edit Manually',
      'Dismiss',
    ])
    expect(actions[0]!.fields).toEqual([{ key: 'status', label: 'Status', value: 'discontinued' }])
    expect(actions[1]!.fields).toEqual([{ key: 'status', label: 'Status', value: 'active' }])
    expect(actions[0]!.editable).toBe(false)
    expect(actions[1]!.editable).toBe(false)
  })

  it('applies the same status conflict actions to the generic status_conflict type', () => {
    const discrepancy = makeDiscrepancy({ discrepancy_type: 'status_conflict', medication })

    const labels = getDiscrepancyActions(discrepancy).map((action) => action.label)

    expect(labels).toEqual(['Mark Discontinued', 'Mark Active', 'Edit Manually', 'Dismiss'])
  })

  it('offers only Edit Manually and Dismiss for an unsupported medication list entry', () => {
    const discrepancy = makeDiscrepancy({
      discrepancy_type: 'unsupported_medication_list_entry',
      medication,
    })

    const labels = getDiscrepancyActions(discrepancy).map((action) => action.label)

    expect(labels).toEqual(['Edit Manually', 'Dismiss'])
  })

  it('Dismiss is always last, has no fields, and is not editable', () => {
    for (const type of [
      'missing_from_medication_list',
      'dose_conflict',
      'discontinued_status_conflict',
      'unsupported_medication_list_entry',
    ] as const) {
      const actions = getDiscrepancyActions(makeDiscrepancy({ discrepancy_type: type }))
      const dismiss = actions[actions.length - 1]!

      expect(dismiss.label).toBe('Dismiss')
      expect(dismiss.action).toBe('dismiss')
      expect(dismiss.fields).toEqual([])
      expect(dismiss.editable).toBe(false)
    }
  })
})

describe('requiredFieldKeys', () => {
  it('requires every medication field for add_medication', () => {
    const addAction = getDiscrepancyActions(
      makeDiscrepancy({ discrepancy_type: 'missing_from_medication_list' }),
    )[0]!

    expect(requiredFieldKeys(addAction)).toEqual([
      'medication_name',
      'dose',
      'route',
      'frequency',
      'status',
    ])
  })

  it('requires nothing for update_medication or dismiss', () => {
    const discrepancy = makeDiscrepancy({
      discrepancy_type: 'dose_conflict',
      medication,
      medication_mention: mention,
    })
    const [updateAction, , dismissAction] = getDiscrepancyActions(discrepancy)

    expect(requiredFieldKeys(updateAction!)).toEqual([])
    expect(requiredFieldKeys(dismissAction!)).toEqual([])
  })
})

describe('buildResolutionPayload', () => {
  it('includes only fields with a non-empty trimmed value', () => {
    const action = getDiscrepancyActions(
      makeDiscrepancy({ discrepancy_type: 'unsupported_medication_list_entry', medication }),
    )[0]! // Edit Manually, all 5 fields present

    const payload = buildResolutionPayload(
      action,
      {
        medication_name: '  Lisinopril  ',
        dose: '',
        route: 'oral',
        frequency: '   ',
        status: 'active',
      },
      '',
    )

    expect(payload).toEqual({
      action: 'update_medication',
      medication_name: 'Lisinopril',
      route: 'oral',
      status: 'active',
    })
  })

  it('includes a trimmed note only when non-empty', () => {
    const dismiss = getDiscrepancyActions(makeDiscrepancy())[1]!

    expect(buildResolutionPayload(dismiss, {}, '  Confirmed by phone.  ')).toEqual({
      action: 'dismiss',
      note: 'Confirmed by phone.',
    })
    expect(buildResolutionPayload(dismiss, {}, '   ')).toEqual({ action: 'dismiss' })
  })
})
