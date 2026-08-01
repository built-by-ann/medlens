import { Input } from '@/components/common/Input'
import type { MedicationPayload } from '@/api/medications'
import type { MedicationFormErrors } from '@/components/medications/medicationFormValidation'

interface MedicationFieldsProps {
  idPrefix: string
  values: MedicationPayload
  errors: MedicationFormErrors
  disabled: boolean
  onChange: (field: keyof MedicationPayload, value: string) => void
}

/**
 * The shared set of fields for both adding a new medication and editing an
 * existing one, so the two forms can't drift out of sync.
 */
export function MedicationFields({
  idPrefix,
  values,
  errors,
  disabled,
  onChange,
}: MedicationFieldsProps) {
  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Input
          label="Medication name"
          value={values.medicationName}
          onChange={(event) => onChange('medicationName', event.target.value)}
          error={errors.medicationName}
          disabled={disabled}
          required
        />
        <Input
          label="Dosage"
          value={values.dose}
          onChange={(event) => onChange('dose', event.target.value)}
          error={errors.dose}
          disabled={disabled}
          placeholder="e.g. 10 mg"
          required
        />
        <Input
          label="Route"
          value={values.route}
          onChange={(event) => onChange('route', event.target.value)}
          error={errors.route}
          disabled={disabled}
          placeholder="e.g. oral"
          required
        />
        <Input
          label="Frequency"
          value={values.frequency}
          onChange={(event) => onChange('frequency', event.target.value)}
          error={errors.frequency}
          disabled={disabled}
          placeholder="e.g. once daily"
          required
        />
        <Input
          label="Status"
          value={values.status}
          onChange={(event) => onChange('status', event.target.value)}
          error={errors.status}
          disabled={disabled}
          placeholder="e.g. active"
          required
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${idPrefix}-notes`} className="text-sm font-medium text-foreground">
          Notes (optional)
        </label>
        <textarea
          id={`${idPrefix}-notes`}
          value={values.notes}
          onChange={(event) => onChange('notes', event.target.value)}
          disabled={disabled}
          rows={3}
          className="w-full rounded-md border border-border px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        />
      </div>
    </>
  )
}
