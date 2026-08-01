import { Input } from '@/components/common/Input'
import type { PatientPayload } from '@/api/patients'
import type { PatientFormErrors } from '@/components/patients/patientFormValidation'

interface PatientFieldsProps {
  idPrefix: string
  values: PatientPayload
  errors: PatientFormErrors
  disabled: boolean
  onChange: (field: keyof PatientPayload, value: string) => void
}

/**
 * The shared set of fields for both creating a new patient and editing an
 * existing one, so the two forms can't drift out of sync.
 */
export function PatientFields({
  idPrefix,
  values,
  errors,
  disabled,
  onChange,
}: PatientFieldsProps) {
  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Input
          label="First name"
          value={values.firstName}
          onChange={(event) => onChange('firstName', event.target.value)}
          error={errors.firstName}
          disabled={disabled}
          required
        />
        <Input
          label="Last name"
          value={values.lastName}
          onChange={(event) => onChange('lastName', event.target.value)}
          error={errors.lastName}
          disabled={disabled}
          required
        />
        <Input
          label="Date of birth"
          type="date"
          value={values.dateOfBirth}
          onChange={(event) => onChange('dateOfBirth', event.target.value)}
          error={errors.dateOfBirth}
          disabled={disabled}
          required
        />
        <Input
          label="External MRN (optional)"
          value={values.externalMrn}
          onChange={(event) => onChange('externalMrn', event.target.value)}
          disabled={disabled}
          placeholder="e.g. MRN-001"
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
