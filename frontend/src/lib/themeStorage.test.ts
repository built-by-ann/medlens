import { beforeEach, describe, expect, it } from 'vitest'
import {
  clearStoredTheme,
  getStoredMode,
  getStoredPalette,
  setStoredMode,
  setStoredPalette,
} from '@/lib/themeStorage'

describe('themeStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  describe('palette', () => {
    it('returns null when no palette has been stored', () => {
      expect(getStoredPalette()).toBeNull()
    })

    it('persists a palette so it can be read back', () => {
      setStoredPalette('blossom')
      expect(getStoredPalette()).toBe('blossom')
    })

    it('overwrites a previously stored palette', () => {
      setStoredPalette('sage')
      setStoredPalette('twilight')
      expect(getStoredPalette()).toBe('twilight')
    })

    it('ignores a value that is not a recognized palette', () => {
      localStorage.setItem('medlens.theme.palette', 'not-a-real-palette')
      expect(getStoredPalette()).toBeNull()
    })
  })

  describe('mode', () => {
    it('returns null when no mode has been stored', () => {
      expect(getStoredMode()).toBeNull()
    })

    it('persists a mode so it can be read back', () => {
      setStoredMode('dark')
      expect(getStoredMode()).toBe('dark')
    })

    it('persists the system preference', () => {
      setStoredMode('system')
      expect(getStoredMode()).toBe('system')
    })

    it('overwrites a previously stored mode', () => {
      setStoredMode('light')
      setStoredMode('high-contrast')
      expect(getStoredMode()).toBe('high-contrast')
    })

    it('ignores a value that is not a recognized mode', () => {
      localStorage.setItem('medlens.theme.mode', 'not-a-real-mode')
      expect(getStoredMode()).toBeNull()
    })
  })

  describe('clearStoredTheme', () => {
    it('removes both the palette and the mode', () => {
      setStoredPalette('coastal')
      setStoredMode('dark')

      clearStoredTheme()

      expect(getStoredPalette()).toBeNull()
      expect(getStoredMode()).toBeNull()
    })

    it('does nothing harmful when clearing when nothing was ever stored', () => {
      expect(() => clearStoredTheme()).not.toThrow()
      expect(getStoredPalette()).toBeNull()
      expect(getStoredMode()).toBeNull()
    })
  })
})
