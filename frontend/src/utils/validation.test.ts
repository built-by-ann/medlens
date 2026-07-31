import { describe, expect, it } from 'vitest'
import { isValidEmail } from '@/utils/validation'

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
