import { beforeEach, describe, expect, it } from 'vitest'
import { clearStoredToken, getStoredToken, setStoredToken } from '@/lib/tokenStorage'

describe('tokenStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns null when no token has been stored', () => {
    expect(getStoredToken()).toBeNull()
  })

  it('persists a token so it can be read back', () => {
    setStoredToken('abc123')

    expect(getStoredToken()).toBe('abc123')
  })

  it('overwrites a previously stored token', () => {
    setStoredToken('first-token')
    setStoredToken('second-token')

    expect(getStoredToken()).toBe('second-token')
  })

  it('removes the token so it reads back as null again', () => {
    setStoredToken('abc123')
    clearStoredToken()

    expect(getStoredToken()).toBeNull()
  })

  it('does nothing harmful when clearing when nothing was ever stored', () => {
    expect(() => clearStoredToken()).not.toThrow()
    expect(getStoredToken()).toBeNull()
  })
})
