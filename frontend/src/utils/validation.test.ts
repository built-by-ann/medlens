import { describe, expect, it } from 'vitest'
import { isValidEmail, usernameFormatError } from '@/utils/validation'

describe('isValidEmail', () => {
  it.each(['a@example.com', 'jane.doe@example.co.uk', 'a+tag@example.com'])(
    'accepts %s',
    (email) => {
      expect(isValidEmail(email)).toBe(true)
    },
  )

  it.each(['', 'not-an-email', 'missing-domain@', '@missing-local.com', 'has space@example.com'])(
    'rejects %s',
    (email) => {
      expect(isValidEmail(email)).toBe(false)
    },
  )

  it('trims surrounding whitespace before validating', () => {
    expect(isValidEmail('  a@example.com  ')).toBe(true)
  })
})

describe('usernameFormatError', () => {
  it.each(['abc', 'a'.repeat(30), 'valid_user.name', 'MixedCase123'])('accepts %s', (username) => {
    expect(usernameFormatError(username)).toBeNull()
  })

  it('rejects a username shorter than 3 characters', () => {
    expect(usernameFormatError('ab')).toMatch(/between 3 and 30/)
  })

  it('rejects a username longer than 30 characters', () => {
    expect(usernameFormatError('a'.repeat(31))).toMatch(/between 3 and 30/)
  })

  it.each(['not valid', 'not-valid', 'invalid@name', 'invalid!'])(
    'rejects %s for containing disallowed characters',
    (username) => {
      expect(usernameFormatError(username)).toMatch(/letters, numbers, underscores, and periods/)
    },
  )
})
