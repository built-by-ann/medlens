import { useState, type FormEvent } from 'react'
import { Card } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { FormError } from '@/components/common/FormError'
import { MedicationFields } from '@/components/medications/MedicationFields'
import {
  EMPTY_MEDICATION_PAYLOAD,
  validateMedicationForm,
  type MedicationFormErrors,
} from '@/components/medications/medicationFormValidation'
import type { ApiError } from '@/api/client'
import type { MedicationPayload } from '@/api/medications'
import type { Medication } from '@/types/api'

interface MedicationFormProps {
  onAdd: (payload: MedicationPayload) => Promise<Medication>
}

export function MedicationForm({ onAdd }: MedicationFormProps) {
  const [values, setValues] = useState<MedicationPayload>(EMPTY_MEDICATION_PAYLOAD)
  const [errors, setErrors] = useState<MedicationFormErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function handleChange(field: keyof MedicationPayload, value: string) {
    setValues((current) => ({ ...current, [field]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSubmitting) return

    const validationErrors = validateMedicationForm(values)
    setErrors(validationErrors)
    setFormError(null)
    if (Object.keys(validationErrors).length > 0) return

    setIsSubmitting(true)
    try {
      await onAdd(values)
      setValues(EMPTY_MEDICATION_PAYLOAD)
      setErrors({})
    } catch (error) {
      setFormError((error as ApiError).message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Card className="flex flex-col gap-4">
      <h3 id="add-medication-heading" className="text-sm font-semibold text-foreground">
        Add a medication
      </h3>
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        {formError && <FormError message={formError} />}
        <MedicationFields
          idPrefix="add-medication"
          values={values}
          errors={errors}
          disabled={isSubmitting}
          onChange={handleChange}
        />
        <Button type="submit" disabled={isSubmitting} className="self-start">
          {isSubmitting ? 'Adding...' : 'Add medication'}
        </Button>
      </form>
    </Card>
  )
}
