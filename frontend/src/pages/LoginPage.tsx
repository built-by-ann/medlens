import { useEffect } from 'react'
import { Link, useLocation, useNavigate, type Location } from 'react-router-dom'
import { Card } from '@/components/common/Card'
import { PageHeader } from '@/components/common/PageHeader'
import { Input } from '@/components/common/Input'
import { Button } from '@/components/common/Button'
import { FormError } from '@/components/common/FormError'
import { useAuth } from '@/hooks/useAuth'
import { useAuthForm } from '@/hooks/useAuthForm'
import type { ApiError } from '@/api/client'
import { isValidEmail } from '@/utils/validation'
import { ROUTES } from '@/routes/paths'

interface LocationState {
  from?: Location
}

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
  const location = useLocation()
  const { login, sessionExpiredMessage, clearSessionExpiredMessage } = useAuth()

  const { values, errors, formError, setFormError, isSubmitting, updateField, handleSubmit } =
    useAuthForm<FormValues>({
      initialValues,
      validate,
      onSubmit: async (values) => {
        try {
          await login(values.email.trim(), values.password)

          const state = location.state as LocationState | null
          const destination = state?.from
            ? `${state.from.pathname}${state.from.search}`
            : ROUTES.dashboard

          navigate(destination, { replace: true })
        } catch (error) {
          const apiError = error as ApiError

          // The backend intentionally returns the same 401 message whether
          // the email doesn't exist or the password is wrong, so a caller
          // can't tell those cases apart. Attaching this to the email or
          // password field individually would leak which one was correct,
          // so every failure here is shown as one form-level message
          // instead.
          setFormError(apiError.message)
        }
      },
    })

  // Surfaces a silent, session-ending logout (the token expired or was
  // revoked) the one time it's read, through the exact same form-level
  // message every other login failure already uses - not a separate banner
  // or toast. Cleared immediately after so it can't reappear on a later
  // visit to this page.
  useEffect(() => {
    if (sessionExpiredMessage) {
      setFormError(sessionExpiredMessage)
      clearSessionExpiredMessage()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionExpiredMessage])

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <PageHeader title="Log in" description="Sign in to your MedLens account." />
        <Card>
          <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
            {formError && <FormError message={formError} />}

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
