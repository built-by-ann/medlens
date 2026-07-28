import { useState, type FormEvent } from 'react'
import { Card } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { SummaryStat } from '@/components/common/SummaryStat'
import { MedicationFields } from '@/components/medications/MedicationFields'
import {
  validateMedicationForm,
  type MedicationFormErrors,
} from '@/components/medications/medicationFormValidation'
import type { ApiError } from '@/api/client'
import type { MedicationPayload } from '@/api/medications'
import type { Medication } from '@/types/api'

function toPayload(medication: Medication): MedicationPayload {
  return {
    medicationName: medication.medication_name,
    dose: medication.dose,
    route: medication.route,
    frequency: medication.frequency,
    status: medication.status,
    notes: medication.notes ?? '',
  }
}

interface MedicationCardProps {
  medication: Medication
  onEdit: (id: number, payload: MedicationPayload) => Promise<Medication>
  onDelete: (id: number) => Promise<void>
}

export function MedicationCard({ medication, onEdit, onDelete }: MedicationCardProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [values, setValues] = useState<MedicationPayload>(() => toPayload(medication))
  const [errors, setErrors] = useState<MedicationFormErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  function startEditing() {
    setValues(toPayload(medication))
    setErrors({})
    setFormError(null)
    setIsEditing(true)
  }

  function handleChange(field: keyof MedicationPayload, value: string) {
    setValues((current) => ({ ...current, [field]: value }))
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSaving) return

    const validationErrors = validateMedicationForm(values)
    setErrors(validationErrors)
    setFormError(null)
    if (Object.keys(validationErrors).length > 0) return

    setIsSaving(true)
    try {
      await onEdit(medication.id, values)
      setIsEditing(false)
    } catch (error) {
      setFormError((error as ApiError).message)
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete() {
    if (isDeleting) return

    setIsDeleting(true)
    setDeleteError(null)
    try {
      await onDelete(medication.id)
    } catch (error) {
      setDeleteError((error as ApiError).message)
      setIsDeleting(false)
    }
  }

  if (isEditing) {
    return (
      <Card className="flex flex-col gap-4">
        <form onSubmit={handleSave} noValidate className="flex flex-col gap-4">
          {formError && (
            <p role="alert" className="text-sm text-red-600">
              {formError}
            </p>
          )}
          <MedicationFields
            idPrefix={`medication-${medication.id}`}
            values={values}
            errors={errors}
            disabled={isSaving}
            onChange={handleChange}
          />
          <div className="flex gap-2">
            <Button type="submit" disabled={isSaving}>
              {isSaving ? 'Saving...' : 'Save'}
            </Button>
            <button
              type="button"
              onClick={() => setIsEditing(false)}
              disabled={isSaving}
              className="cursor-pointer rounded-md px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            >
              Cancel
            </button>
          </div>
        </form>
      </Card>
    )
  }

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <h4 className="text-sm font-semibold text-slate-900">{medication.medication_name}</h4>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={startEditing}
            className="cursor-pointer rounded-md px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            Edit
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={isDeleting}
            aria-label={`Delete ${medication.medication_name}`}
            className="cursor-pointer rounded-md px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isDeleting ? 'Removing...' : 'Delete'}
          </button>
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryStat label="Dosage" value={medication.dose} />
        <SummaryStat label="Route" value={medication.route} />
        <SummaryStat label="Frequency" value={medication.frequency} />
        <SummaryStat label="Status" value={medication.status} />
      </dl>
      {medication.notes && <p className="text-sm text-slate-600">{medication.notes}</p>}
      {deleteError && (
        <p role="alert" className="text-sm text-red-600">
          {deleteError}
        </p>
      )}
    </Card>
  )
}
