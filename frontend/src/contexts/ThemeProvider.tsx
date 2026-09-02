import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ThemeContext, type ThemeContextValue } from '@/contexts/ThemeContext'
import {
  getStoredMode,
  getStoredPalette,
  setStoredMode,
  setStoredPalette,
  type Mode,
  type ModePreference,
  type PaletteName,
} from '@/lib/themeStorage'

const SYSTEM_DARK_QUERY = '(prefers-color-scheme: dark)'

function resolveSystemMode(): Mode {
  return window.matchMedia(SYSTEM_DARK_QUERY).matches ? 'dark' : 'light'
}

interface ThemeProviderProps {
  children: ReactNode
}

/**
 * Owns the active palette and mode, and applies their combination to the
 * document. A theme is switched by setting `data-theme="{palette}-{mode}"`
 * on `<html>`; every color in the app is a CSS custom property keyed off
 * that attribute (see src/styles/themes.css), so this component never needs
 * to know what any theme actually looks like.
 *
 * Palette and mode are independent, both persisted, both restored on load.
 * If no mode was ever stored, it defaults to 'system': the OS's
 * prefers-color-scheme decides light vs dark, matching every other
 * `system`-aware application, and a matchMedia listener keeps it in sync
 * with OS changes made while the app is open. Palette has no OS-level
 * equivalent, so it simply defaults to 'default' when nothing is stored.
 */
export function ThemeProvider({ children }: ThemeProviderProps) {
  const [palette, setPaletteState] = useState<PaletteName>(() => getStoredPalette() ?? 'default')
  const [modePreference, setModePreferenceState] = useState<ModePreference>(
    () => getStoredMode() ?? 'system',
  )
  // Tracks only the OS preference itself, kept up to date by a single,
  // permanent matchMedia subscription below, not by an effect reacting to
  // `modePreference`. `resolvedMode` is then a plain derived value, never
  // its own piece of state that needs syncing.
  const [systemMode, setSystemMode] = useState<Mode>(() => resolveSystemMode())

  const resolvedMode = modePreference === 'system' ? systemMode : modePreference
  const resolvedTheme = `${palette}-${resolvedMode}` as const

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', resolvedTheme)
  }, [resolvedTheme])

  useEffect(() => {
    const query = window.matchMedia(SYSTEM_DARK_QUERY)
    const handleChange = () => setSystemMode(resolveSystemMode())

    query.addEventListener('change', handleChange)
    return () => query.removeEventListener('change', handleChange)
  }, [])

  const setPalette = useCallback((next: PaletteName) => {
    setStoredPalette(next)
    setPaletteState(next)
  }, [])

  const setModePreference = useCallback((next: ModePreference) => {
    setStoredMode(next)
    setModePreferenceState(next)
  }, [])

  const value = useMemo<ThemeContextValue>(
    () => ({ palette, modePreference, resolvedMode, resolvedTheme, setPalette, setModePreference }),
    [palette, modePreference, resolvedMode, resolvedTheme, setPalette, setModePreference],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
