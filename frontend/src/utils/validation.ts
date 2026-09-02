const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function isValidEmail(value: string): boolean {
  return EMAIL_PATTERN.test(value.trim())
}

// Mirrors backend/app/schemas/user.py's validate_username_format exactly;
// registration (required) and profile updates (optional) both need the
// same rules, so this stays in one place rather than each page re-deriving
// them. Deliberately does not check "required" itself (unlike the backend
// schema, where username is always present by the time this runs); a
// missing value means different things on each page (Signup: an error;
// Profile: "leave it as-is" or "clear it"), so each page's own validate()
// checks that first, the same way both pages already handle email.
export const USERNAME_MIN_LENGTH = 3
export const USERNAME_MAX_LENGTH = 30
const USERNAME_PATTERN = /^[A-Za-z0-9_.]+$/

export function usernameFormatError(value: string): string | null {
  if (value.length < USERNAME_MIN_LENGTH || value.length > USERNAME_MAX_LENGTH) {
    return `Username must be between ${USERNAME_MIN_LENGTH} and ${USERNAME_MAX_LENGTH} characters.`
  }

  if (!USERNAME_PATTERN.test(value)) {
    return 'Username may only contain letters, numbers, underscores, and periods.'
  }

  return null
}
