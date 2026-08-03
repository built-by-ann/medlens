import type { ChangeEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Card } from '@/components/common/Card'
import { PageHeader } from '@/components/common/PageHeader'
import { Input } from '@/components/common/Input'
import { Button } from '@/components/common/Button'
import { FormError } from '@/components/common/FormError'
import { registerUser } from '@/api/auth'
import { useAuthForm } from '@/hooks/useAuthForm'
import type { ApiError } from '@/api/client'
import { isValidEmail, usernameFormatError } from '@/utils/validation'
import { ROUTES } from '@/routes/paths'

const MIN_PASSWORD_LENGTH = 8

interface FormValues {
  fullName: string
  username: string
  email: string
  password: string
  confirmPassword: string
}

type FormErrors = Partial<Record<keyof FormValues, string>>

const initialValues: FormValues = {
  fullName: '',
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
}

function validate(values: FormValues): FormErrors {
  const errors: FormErrors = {}

  if (!values.fullName.trim()) {
    errors.fullName = 'Full name is required.'
  }

  if (!values.username.trim()) {
    errors.username = 'Username is required.'
  } else {
    const formatError = usernameFormatError(values.username.trim())
    if (formatError) {
      errors.username = formatError
    }
  }

  if (!values.email.trim()) {
    errors.email = 'Email is required.'
  } else if (!isValidEmail(values.email)) {
    errors.email = 'Enter a valid email address.'
  }

  if (!values.password) {
    errors.password = 'Password is required.'
  } else if (values.password.length < MIN_PASSWORD_LENGTH) {
    errors.password = `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`
  }

  if (!values.confirmPassword) {
    errors.confirmPassword = 'Please confirm your password.'
  } else if (values.password !== values.confirmPassword) {
    errors.confirmPassword = 'Passwords do not match.'
  }

  return errors
}

export function SignupPage() {
  const navigate = useNavigate()

  const {
    values,
    errors,
    formError,
    setFormError,
    setFieldError,
    isSubmitting,
    updateField,
    handleSubmit,
  } = useAuthForm<FormValues>({
    initialValues,
    validate,
    onSubmit: async (values) => {
      try {
        await registerUser({
          email: values.email.trim(),
          password: values.password,
          username: values.username.trim(),
          name: values.fullName.trim(),
        })

        navigate(ROUTES.login, { replace: true })
      } catch (error) {
        const apiError = error as ApiError

        // A duplicate email or username is specifically about that one
        // field, so it is shown inline like any other field error rather
        // than as a generic banner - distinguished by the backend's own
        // message text, since both failures share the same 409 status.
        // Every other failure (unexpected validation issues, network
        // errors) is shown as a single form-level message instead, since it
        // is not clearly attributable to one field.
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

  // Validates on every keystroke, not just on submit (unlike every other
  // field here) - format mistakes are cheap to catch immediately, and a
  // username has more ways to be malformed (length, character set) than
  // this form's other fields. Clearing the error is just as immediate:
  // setFieldError('username', '') is falsy, so Input renders no error at
  // all - see Input's own `{error && ...}` check.
  function handleUsernameChange(event: ChangeEvent<HTMLInputElement>) {
    updateField('username')(event)

    const trimmed = event.target.value.trim()
    setFieldError('username', trimmed ? (usernameFormatError(trimmed) ?? '') : '')
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <PageHeader title="Create an account" description="Sign up for MedLens." />
        <Card>
          <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
            {formError && <FormError message={formError} />}

            <Input
              label="Full Name"
              name="fullName"
              type="text"
              autoComplete="name"
              value={values.fullName}
              onChange={updateField('fullName')}
              error={errors.fullName}
              disabled={isSubmitting}
              required
            />
            <Input
              label="Username"
              name="username"
              type="text"
              autoComplete="username"
              value={values.username}
              onChange={handleUsernameChange}
              error={errors.username}
              disabled={isSubmitting}
              required
            />
            <Input
              label="Email"
              name="email"
              type="email"
              autoComplete="email"
              value={values.email}
              onChange={updateField('email')}
              error={errors.email}
              disabled={isSubmitting}
              required
            />
            <Input
              label="Password"
              name="password"
              type="password"
              autoComplete="new-password"
              value={values.password}
              onChange={updateField('password')}
              error={errors.password}
              disabled={isSubmitting}
              required
            />
            <Input
              label="Confirm Password"
              name="confirmPassword"
              type="password"
              autoComplete="new-password"
              value={values.confirmPassword}
              onChange={updateField('confirmPassword')}
              error={errors.confirmPassword}
              disabled={isSubmitting}
              required
            />

            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Creating account...' : 'Create account'}
            </Button>

            <p className="text-center text-sm text-muted">
              Already have an account?{' '}
              <Link to={ROUTES.login} className="font-medium text-link hover:underline">
                Log in
              </Link>
            </p>
          </form>
        </Card>
      </div>
    </div>
  )
}
