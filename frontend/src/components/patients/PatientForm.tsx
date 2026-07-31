import { useState, type FormEvent } from 'react'
import { Card } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { FormError } from '@/components/common/FormError'
import { PatientFields } from '@/components/patients/PatientFields'
import {
  EMPTY_PATIENT_PAYLOAD,
  validatePatientForm,
  type PatientFormErrors,
} from '@/components/patients/patientFormValidation'
import type { ApiError } from '@/api/client'
import type { PatientPayload } from '@/api/patients'

interface PatientFormProps {
  initialValues?: PatientPayload
  submitLabel: string
  onSubmit: (payload: PatientPayload) => Promise<void>
}

/**
 * Shared by NewPatientPage and EditPatientPage. Unlike MedicationForm, it
 * never clears itself after a successful submit - both callers navigate
 * away entirely (to the new/edited patient's overview) on success, so
 * there's no "submit again" case to reset for.
 */
export function PatientForm({
  initialValues = EMPTY_PATIENT_PAYLOAD,
  submitLabel,
  onSubmit,
}: PatientFormProps) {
  const [values, setValues] = useState<PatientPayload>(initialValues)
  const [errors, setErrors] = useState<PatientFormErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function handleChange(field: keyof PatientPayload, value: string) {
    setValues((current) => ({ ...current, [field]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSubmitting) return

    const validationErrors = validatePatientForm(values)
    setErrors(validationErrors)
    setFormError(null)
    if (Object.keys(validationErrors).length > 0) return

    setIsSubmitting(true)
    try {
      await onSubmit(values)
    } catch (error) {
      setFormError((error as ApiError).message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Card className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        {formError && <FormError message={formError} />}
        <PatientFields
          idPrefix="patient-form"
          values={values}
          errors={errors}
          disabled={isSubmitting}
          onChange={handleChange}
        />
        <Button type="submit" disabled={isSubmitting} className="self-start">
          {isSubmitting ? 'Saving...' : submitLabel}
        </Button>
      </form>
    </Card>
  )
}
