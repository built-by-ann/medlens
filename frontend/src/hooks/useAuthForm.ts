import { useState, type ChangeEvent, type FormEvent } from 'react'

type FormErrors<Values> = Partial<Record<keyof Values, string>>

interface UseAuthFormOptions<Values extends object> {
  initialValues: Values
  validate: (values: Values) => FormErrors<Values>
  onSubmit: (values: Values) => Promise<void>
}

/**
 * Shared field state, loading state, and submit orchestration for the
 * Login and Signup forms. Deliberately does not own validation rules or
 * error handling: `validate` and `onSubmit` are supplied by each page, so
 * what happens on a validation failure or a backend error stays entirely
 * page-specific (e.g. Signup attaches a 409 to the email field, Login
 * never attaches its 401 to any field). This is a small, form-specific
 * hook for these two forms, not a general-purpose form framework.
 */
export function useAuthForm<Values extends object>({
  initialValues,
  validate,
  onSubmit,
}: UseAuthFormOptions<Values>) {
  const [values, setValues] = useState<Values>(initialValues)
  const [errors, setErrors] = useState<FormErrors<Values>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function updateField(field: keyof Values) {
    return (event: ChangeEvent<HTMLInputElement>) => {
      // Every field on these forms is a plain text/email/password input, so
      // its value is always a string; a generic constraint precise enough
      // to express that structurally (Record<string, string>) would force
      // every page's FormValues interface to carry an index signature just
      // to satisfy it, weakening property-access type-checking for no real
      // benefit. The assertion is confined to this one line.
      setValues((current) => ({ ...current, [field]: event.target.value }) as Values)
    }
  }

  function setFieldError(field: keyof Values, message: string) {
    setErrors((current) => ({ ...current, [field]: message }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (isSubmitting) {
      return
    }

    const validationErrors = validate(values)
    setErrors(validationErrors)
    setFormError(null)

    if (Object.keys(validationErrors).length > 0) {
      return
    }

    setIsSubmitting(true)

    try {
      // onSubmit is expected to handle its own errors (validation-adjacent
      // backend failures, navigation on success); it is not expected to
      // throw. This try/finally exists only to guarantee isSubmitting is
      // always reset, regardless of how onSubmit resolves.
      await onSubmit(values)
    } finally {
      setIsSubmitting(false)
    }
  }

  return {
    values,
    errors,
    formError,
    setFormError,
    setFieldError,
    isSubmitting,
    updateField,
    handleSubmit,
  }
}
