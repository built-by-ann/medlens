import { useState } from 'react'
import { Card } from '@/components/common/Card'
import { Input } from '@/components/common/Input'
import { Button } from '@/components/common/Button'
import { FormError } from '@/components/common/FormError'
import { updateUser } from '@/api/auth'
import { useAuth } from '@/hooks/useAuth'
import { useAuthForm } from '@/hooks/useAuthForm'
import {
  joinName,
  splitName,
  validateProfileForm,
  type ProfileFormValues,
} from '@/components/settings/profileFormValidation'
import type { ApiError } from '@/api/client'

export function ProfileSettings() {
  const { user, setUser } = useAuth()
  const [isSaved, setIsSaved] = useState(false)

  const { firstName, lastName } = splitName(user?.name ?? null)
  const initialValues: ProfileFormValues = {
    firstName,
    lastName,
    email: user?.email ?? '',
  }

  const {
    values,
    errors,
    formError,
    setFormError,
    setFieldError,
    isSubmitting,
    updateField,
    handleSubmit,
  } = useAuthForm<ProfileFormValues>({
    initialValues,
    validate: validateProfileForm,
    onSubmit: async (values) => {
      setIsSaved(false)

      try {
        const updated = await updateUser({
          name: joinName(values.firstName, values.lastName),
          email: values.email.trim(),
        })

        setUser(updated)
        setIsSaved(true)
      } catch (error) {
        const apiError = error as ApiError

        // A duplicate email is specifically about the email field, mirroring
        // how SignupPage attaches its own 409 - every other failure is a
        // generic form-level message instead.
        if (apiError.status === 409) {
          setFieldError('email', apiError.message)
        } else {
          setFormError(apiError.message)
        }
      }
    },
  })

  return (
    <Card className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold text-foreground">Profile</h2>
        <p className="mt-1 text-sm text-muted">Your account information.</p>
      </div>

      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        {formError && <FormError message={formError} />}
        {isSaved && (
          <p role="status" className="text-sm text-success">
            Profile updated.
          </p>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            label="First Name"
            name="firstName"
            autoComplete="given-name"
            value={values.firstName}
            onChange={updateField('firstName')}
            error={errors.firstName}
            disabled={isSubmitting}
            required
          />
          <Input
            label="Last Name"
            name="lastName"
            autoComplete="family-name"
            value={values.lastName}
            onChange={updateField('lastName')}
            error={errors.lastName}
            disabled={isSubmitting}
            required
          />
        </div>

        <Input
          label="Username"
          value=""
          disabled
          placeholder="Not available yet"
          aria-describedby="username-unavailable-note"
        />
        <p id="username-unavailable-note" className="text-xs text-muted">
          A separate username isn't supported yet - MedLens accounts are identified by email.
          Requires a backend update (see docs/frontend.md).
        </p>

        <Input
          label="Email Address"
          name="email"
          type="email"
          autoComplete="email"
          value={values.email}
          onChange={updateField('email')}
          error={errors.email}
          disabled={isSubmitting}
          required
        />

        <Button type="submit" disabled={isSubmitting} className="self-start">
          {isSubmitting ? 'Saving...' : 'Save Changes'}
        </Button>
      </form>
    </Card>
  )
}
