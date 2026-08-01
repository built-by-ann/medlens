import type {
  DiscrepancyResolutionPayload,
  MedicationDiscrepancy,
  ResolutionAction,
} from '@/types/api'

export type MedicationFieldKey = 'medication_name' | 'dose' | 'route' | 'frequency' | 'status'

export interface MedicationFieldValue {
  key: MedicationFieldKey
  label: string
  value: string
}

export interface DiscrepancyActionDescriptor {
  // Unique within one discrepancy's action list - not globally unique.
  key: string
  label: string
  action: ResolutionAction
  // true: opens a dialog with every field as an editable input, pre-filled
  // as a starting point the provider can change before confirming ("Edit
  // Manually", and "Add Medication" since there's real data to enter).
  // false: opens a confirm-only dialog stating exactly what will happen,
  // with no editable medication fields - the fast path for accepting a
  // single suggested value as-is.
  editable: boolean
  fields: MedicationFieldValue[]
  description: string
}

const FIELD_LABELS: Record<MedicationFieldKey, string> = {
  medication_name: 'Medication name',
  dose: 'Dose',
  route: 'Route',
  frequency: 'Frequency',
  status: 'Status',
}

const MEDICATION_FIELD_KEYS: MedicationFieldKey[] = [
  'medication_name',
  'dose',
  'route',
  'frequency',
  'status',
]

// The medication list's own current values - the starting point for "Edit
// Manually", since correcting an existing entry should start from what it
// already says, not from the (possibly wrong) AI-reported value.
function currentMedicationFields(discrepancy: MedicationDiscrepancy): MedicationFieldValue[] {
  const medication = discrepancy.medication

  return MEDICATION_FIELD_KEYS.map((key) => ({
    key,
    label: FIELD_LABELS[key],
    value: medication?.[key] ?? '',
  }))
}

// What the AI actually extracted - the starting point for "Add Medication",
// since there is no existing medication list entry to start from.
function mentionFields(discrepancy: MedicationDiscrepancy): MedicationFieldValue[] {
  const mention = discrepancy.medication_mention

  return MEDICATION_FIELD_KEYS.map((key) => ({
    key,
    label: FIELD_LABELS[key],
    value: mention?.[key] ?? '',
  }))
}

// A single field's suggested value, straight from the AI's mention - null
// when the mention never reported it, so the caller can skip offering a
// one-click "Update Medication" quick action with nothing concrete to apply
// (falling back to Edit Manually only, per "do not expose actions that
// don't make sense for this discrepancy").
function singleFieldFromMention(
  discrepancy: MedicationDiscrepancy,
  key: Exclude<MedicationFieldKey, 'medication_name'>,
): MedicationFieldValue[] | null {
  const value = discrepancy.medication_mention?.[key]

  if (!value) return null

  return [{ key, label: FIELD_LABELS[key], value }]
}

const EDIT_MANUALLY: Omit<DiscrepancyActionDescriptor, 'fields'> = {
  key: 'edit',
  label: 'Edit Manually',
  action: 'update_medication',
  editable: true,
  description: "Review and correct the medication's details directly.",
}

const DISMISS: DiscrepancyActionDescriptor = {
  key: 'dismiss',
  label: 'Dismiss',
  action: 'dismiss',
  editable: false,
  fields: [],
  description: 'Dismiss this finding without changing the medication list.',
}

/**
 * The actions available for one discrepancy, in display order - matches
 * the issue's own examples exactly (missing -> Add Medication/Dismiss;
 * dose/route/frequency conflicts -> Update Medication/Edit Manually/Dismiss;
 * status conflicts -> Mark Discontinued/Mark Active/Edit Manually/Dismiss;
 * unsupported list entry -> Edit Manually/Dismiss). Dismiss is always last
 * and always available - resolving is optional, dismissing never is.
 */
export function getDiscrepancyActions(
  discrepancy: MedicationDiscrepancy,
): DiscrepancyActionDescriptor[] {
  const actions: DiscrepancyActionDescriptor[] = []

  switch (discrepancy.discrepancy_type) {
    case 'missing_from_medication_list':
      actions.push({
        key: 'add',
        label: 'Add Medication',
        action: 'add_medication',
        editable: true,
        fields: mentionFields(discrepancy),
        description: "Add this medication to the patient's medication list.",
      })
      break

    case 'dose_conflict':
    case 'route_conflict':
    case 'frequency_conflict': {
      const key: MedicationFieldKey =
        discrepancy.discrepancy_type === 'dose_conflict'
          ? 'dose'
          : discrepancy.discrepancy_type === 'route_conflict'
            ? 'route'
            : 'frequency'
      const suggested = singleFieldFromMention(discrepancy, key)

      if (suggested) {
        actions.push({
          key: 'update',
          label: 'Update Medication',
          action: 'update_medication',
          editable: false,
          fields: suggested,
          description: `Update ${FIELD_LABELS[key].toLowerCase()} to "${suggested[0]!.value}".`,
        })
      }

      actions.push({ ...EDIT_MANUALLY, fields: currentMedicationFields(discrepancy) })
      break
    }

    case 'discontinued_status_conflict':
    case 'status_conflict':
      actions.push({
        key: 'mark_discontinued',
        label: 'Mark Discontinued',
        action: 'update_medication',
        editable: false,
        fields: [{ key: 'status', label: FIELD_LABELS.status, value: 'discontinued' }],
        description: "Set this medication's status to discontinued.",
      })
      actions.push({
        key: 'mark_active',
        label: 'Mark Active',
        action: 'update_medication',
        editable: false,
        fields: [{ key: 'status', label: FIELD_LABELS.status, value: 'active' }],
        description: "Set this medication's status to active.",
      })
      actions.push({ ...EDIT_MANUALLY, fields: currentMedicationFields(discrepancy) })
      break

    case 'unsupported_medication_list_entry':
      actions.push({
        ...EDIT_MANUALLY,
        description: 'Review and correct this medication list entry directly.',
        fields: currentMedicationFields(discrepancy),
      })
      break
  }

  actions.push(DISMISS)

  return actions
}

/** Every field required to enable the Confirm button - add_medication needs
 * all five (a real Medication row has none optional); update_medication
 * needs at least one (enforced by the caller, not per-field here); dismiss
 * needs none. */
export function requiredFieldKeys(action: DiscrepancyActionDescriptor): MedicationFieldKey[] {
  return action.action === 'add_medication' ? MEDICATION_FIELD_KEYS : []
}

export function buildResolutionPayload(
  action: DiscrepancyActionDescriptor,
  fieldValues: Record<string, string>,
  note: string,
): DiscrepancyResolutionPayload {
  const payload: DiscrepancyResolutionPayload = { action: action.action }

  for (const field of action.fields) {
    const value = (fieldValues[field.key] ?? '').trim()

    if (value) {
      payload[field.key] = value
    }
  }

  const trimmedNote = note.trim()
  if (trimmedNote) {
    payload.note = trimmedNote
  }

  return payload
}
