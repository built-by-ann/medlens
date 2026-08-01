import { isValidEmail } from '@/utils/validation'

export interface ProfileFormValues {
  firstName: string
  lastName: string
  email: string
}

export type ProfileFormErrors = Partial<Record<keyof ProfileFormValues, string>>

export function validateProfileForm(values: ProfileFormValues): ProfileFormErrors {
  const errors: ProfileFormErrors = {}

  if (!values.firstName.trim()) {
    errors.firstName = 'First name is required.'
  }

  if (!values.lastName.trim()) {
    errors.lastName = 'Last name is required.'
  }

  if (!values.email.trim()) {
    errors.email = 'Email is required.'
  } else if (!isValidEmail(values.email)) {
    errors.email = 'Enter a valid email address.'
  }

  return errors
}

// The backend only stores a single `name` column (see docs/frontend.md's
// Settings section, and backend/app/models/user.py) - there is no separate
// first_name/last_name split to persist. Splitting/joining happens only
// here, client-side, as a display convenience: the first word becomes
// "First name", everything after it becomes "Last name". A name with more
// than two words round-trips correctly (the whole remainder is preserved
// as "Last name"), but this is necessarily a heuristic, not a real
// structured field - see PROFILE_BACKEND_GAPS in ProfileSettings.tsx.
export function splitName(name: string | null): { firstName: string; lastName: string } {
  const trimmed = (name ?? '').trim()

  if (!trimmed) {
    return { firstName: '', lastName: '' }
  }

  const [firstName = '', ...rest] = trimmed.split(/\s+/)

  return { firstName, lastName: rest.join(' ') }
}

export function joinName(firstName: string, lastName: string): string | null {
  const joined = `${firstName.trim()} ${lastName.trim()}`.trim()

  return joined || null
}
