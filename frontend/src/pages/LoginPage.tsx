import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Card } from '@/components/common/Card'
import { PageHeader } from '@/components/common/PageHeader'
import { Input } from '@/components/common/Input'
import { Button } from '@/components/common/Button'
import { loginUser } from '@/api/auth'
import type { ApiError } from '@/api/client'
import { isValidEmail } from '@/utils/validation'
import { ROUTES } from '@/routes/paths'

interface FormValues {
  email: string
  password: string
}

type FormErrors = Partial<Record<keyof FormValues, string>>

const initialValues: FormValues = {
  email: '',
  password: '',
}

function validate(values: FormValues): FormErrors {
  const errors: FormErrors = {}

  if (!values.email.trim()) {
    errors.email = 'Email is required.'
  } else if (!isValidEmail(values.email)) {
    errors.email = 'Enter a valid email address.'
  }

  if (!values.password) {
    errors.password = 'Password is required.'
  }

  return errors
}

export function LoginPage() {
  const navigate = useNavigate()
  const [values, setValues] = useState<FormValues>(initialValues)
  const [errors, setErrors] = useState<FormErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function updateField(field: keyof FormValues) {
    return (event: ChangeEvent<HTMLInputElement>) => {
      setValues((current) => ({ ...current, [field]: event.target.value }))
    }
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
      // The returned token is intentionally discarded. Storing it and
      // updating AuthContext is out of scope for this issue; see the TODO
      // below.
      await loginUser({
        email: values.email.trim(),
        password: values.password,
      })

      // TODO(auth-state-management): This redirect is a placeholder. Once
      // AuthContext is implemented, this should store the returned token,
      // update AuthContext with the authenticated user, and redirect based
      // on that state (e.g. back to wherever the user was headed) instead
      // of always navigating straight to the dashboard.
      navigate(ROUTES.dashboard, { replace: true })
    } catch (error) {
      const apiError = error as ApiError

      // The backend intentionally returns the same 401 message whether the
      // email doesn't exist or the password is wrong, so a caller can't
      // tell those cases apart. Attaching this to the email or password
      // field individually would leak which one was correct, so every
      // failure here is shown as one form-level message instead.
      setFormError(apiError.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <PageHeader title="Log in" description="Sign in to your MedLens account." />
        <Card>
          <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
            {formError && (
              <p role="alert" className="text-sm text-red-600">
                {formError}
              </p>
            )}

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
              autoComplete="current-password"
              value={values.password}
              onChange={updateField('password')}
              error={errors.password}
              disabled={isSubmitting}
              required
            />

            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Logging in...' : 'Log in'}
            </Button>

            <p className="text-center text-sm text-slate-600">
              Don&apos;t have an account?{' '}
              <Link to={ROUTES.signup} className="font-medium text-blue-600 hover:underline">
                Sign up
              </Link>
            </p>
          </form>
        </Card>
      </div>
    </div>
  )
}
