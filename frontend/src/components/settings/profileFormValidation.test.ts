import { describe, expect, it } from 'vitest'
import {
  joinName,
  splitName,
  validateProfileForm,
  type ProfileFormValues,
} from '@/components/settings/profileFormValidation'

const validValues: ProfileFormValues = {
  firstName: 'Ann',
  lastName: 'Mathew',
  username: 'annm',
  email: 'ann@example.com',
}

describe('validateProfileForm', () => {
  it('returns no errors for fully valid values', () => {
    expect(validateProfileForm(validValues)).toEqual({})
  })

  it('requires first name, last name, and email, but not username', () => {
    expect(validateProfileForm({ firstName: '', lastName: '', username: '', email: '' })).toEqual({
      firstName: 'First name is required.',
      lastName: 'Last name is required.',
      email: 'Email is required.',
    })
  })

  it('rejects a malformed username, when one is present', () => {
    expect(validateProfileForm({ ...validValues, username: 'ab' })).toEqual({
      username: 'Username must be between 3 and 30 characters.',
    })
  })

  it('accepts a blank username, it means "leave unset", not an error', () => {
    expect(validateProfileForm({ ...validValues, username: '' })).toEqual({})
  })

  it('treats a whitespace-only value as missing', () => {
    expect(validateProfileForm({ ...validValues, firstName: '   ' })).toEqual({
      firstName: 'First name is required.',
    })
  })

  it('rejects an invalid email format', () => {
    expect(validateProfileForm({ ...validValues, email: 'not-an-email' })).toEqual({
      email: 'Enter a valid email address.',
    })
  })

  it('reports only the fields that are actually invalid', () => {
    expect(validateProfileForm({ ...validValues, lastName: '' })).toEqual({
      lastName: 'Last name is required.',
    })
  })
})

describe('splitName', () => {
  it('splits a two-word name into first and last', () => {
    expect(splitName('Ann Mathew')).toEqual({ firstName: 'Ann', lastName: 'Mathew' })
  })

  it('preserves every word after the first as the last name', () => {
    expect(splitName('Ann Marie Mathew')).toEqual({ firstName: 'Ann', lastName: 'Marie Mathew' })
  })

  it('treats a single-word name as first name only', () => {
    expect(splitName('Ann')).toEqual({ firstName: 'Ann', lastName: '' })
  })

  it('returns empty strings for null', () => {
    expect(splitName(null)).toEqual({ firstName: '', lastName: '' })
  })

  it('returns empty strings for an empty or whitespace-only name', () => {
    expect(splitName('   ')).toEqual({ firstName: '', lastName: '' })
  })

  it('collapses repeated internal whitespace', () => {
    expect(splitName('Ann   Mathew')).toEqual({ firstName: 'Ann', lastName: 'Mathew' })
  })
})

describe('joinName', () => {
  it('joins first and last name with a single space', () => {
    expect(joinName('Ann', 'Mathew')).toBe('Ann Mathew')
  })

  it('trims each part before joining', () => {
    expect(joinName('  Ann  ', '  Mathew  ')).toBe('Ann Mathew')
  })

  it('returns null when both parts are empty', () => {
    expect(joinName('', '')).toBeNull()
  })

  it('round-trips through splitName for a simple two-word name', () => {
    const { firstName, lastName } = splitName('Ann Mathew')
    expect(joinName(firstName, lastName)).toBe('Ann Mathew')
  })
})
