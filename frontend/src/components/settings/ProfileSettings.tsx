import { useState, type ChangeEvent } from 'react'
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
import { usernameFormatError } from '@/utils/validation'
import type { ApiError } from '@/api/client'

export function ProfileSettings() {
  const { user, setUser } = useAuth()
  const [isSaved, setIsSaved] = useState(false)

  const { firstName, lastName } = splitName(user?.name ?? null)
  const initialValues: ProfileFormValues = {
    firstName,
    lastName,
    username: user?.username ?? '',
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
        const trimmedUsername = values.username.trim()
        const updated = await updateUser({
          name: joinName(values.firstName, values.lastName),
          // An empty field means "clear it" (existing accounts may have no
          // username at all, see Issue #191) - never send '', which would
          // fail the backend's own min-length check for a value that was
          // actually meant to mean "unset."
          username: trimmedUsername || null,
          email: values.email.trim(),
        })

        setUser(updated)
        setIsSaved(true)
      } catch (error) {
        const apiError = error as ApiError

        // A duplicate email or username is specifically about that one
        // field, mirroring how SignupPage attaches its own 409 - every
        // other failure is a generic form-level message instead.
        if (apiError.status === 409 && apiError.message.toLowerCase().includes('username')) {
          setFieldError('username', apiError.message)
        } else if (apiError.status === 409) {
          setFieldError('email', apiError.message)
        } else {
          setFormError(apiError.message)
        }
      }
    },
  })

  // Same live-validation behavior as SignupPage's username field - see its
  // own comment for why this one field validates on every keystroke
  // instead of only on submit.
  function handleUsernameChange(event: ChangeEvent<HTMLInputElement>) {
    updateField('username')(event)

    const trimmed = event.target.value.trim()
    setFieldError('username', trimmed ? (usernameFormatError(trimmed) ?? '') : '')
  }

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
          name="username"
          autoComplete="username"
          value={values.username}
          onChange={handleUsernameChange}
          error={errors.username}
          disabled={isSubmitting}
          placeholder="Choose a username"
        />

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
