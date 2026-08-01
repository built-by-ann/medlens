import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ThemeProvider } from '@/contexts/ThemeProvider'
import { useTheme } from '@/hooks/useTheme'
import type { ModePreference, PaletteName } from '@/lib/themeStorage'

function Harness() {
  const { palette, modePreference, resolvedMode, resolvedTheme, setPalette, setModePreference } =
    useTheme()

  return (
    <div>
      <span data-testid="palette">{palette}</span>
      <span data-testid="mode-preference">{modePreference}</span>
      <span data-testid="resolved-mode">{resolvedMode}</span>
      <span data-testid="resolved-theme">{resolvedTheme}</span>
      <button onClick={() => setPalette('twilight')}>Set twilight palette</button>
      <button onClick={() => setModePreference('dark')}>Set dark</button>
      <button onClick={() => setModePreference('system')}>Set system</button>
    </div>
  )
}

function renderTheme() {
  return render(
    <ThemeProvider>
      <Harness />
    </ThemeProvider>,
  )
}

function mockMatchMedia(matchesDark: boolean) {
  const listeners = new Set<(event: { matches: boolean }) => void>()

  const mql = {
    matches: matchesDark,
    media: '(prefers-color-scheme: dark)',
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: (_event: string, listener: (event: { matches: boolean }) => void) => {
      listeners.add(listener)
    },
    removeEventListener: (_event: string, listener: (event: { matches: boolean }) => void) => {
      listeners.delete(listener)
    },
    dispatchEvent: () => false,
  }

  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue(mql))

  return {
    fireChange(matches: boolean) {
      mql.matches = matches
      act(() => {
        listeners.forEach((listener) => listener({ matches }))
      })
    },
  }
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('defaults to the default palette and the system mode (light) when nothing is stored', () => {
    mockMatchMedia(false)
    renderTheme()

    expect(screen.getByTestId('palette')).toHaveTextContent('default')
    expect(screen.getByTestId('mode-preference')).toHaveTextContent('system')
    expect(screen.getByTestId('resolved-mode')).toHaveTextContent('light')
    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('default-light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('default-light')
  })

  it('resolves system mode to dark when the OS preference is dark', () => {
    mockMatchMedia(true)
    renderTheme()

    expect(screen.getByTestId('resolved-mode')).toHaveTextContent('dark')
    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('default-dark')
  })

  it('restores a previously stored palette and mode, ignoring the OS preference', () => {
    localStorage.setItem('medlens.theme.palette', 'twilight' satisfies PaletteName)
    localStorage.setItem('medlens.theme.mode', 'high-contrast' satisfies ModePreference)
    mockMatchMedia(false)
    renderTheme()

    expect(screen.getByTestId('palette')).toHaveTextContent('twilight')
    expect(screen.getByTestId('mode-preference')).toHaveTextContent('high-contrast')
    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('twilight-high-contrast')
    expect(document.documentElement.getAttribute('data-theme')).toBe('twilight-high-contrast')
  })

  it('applies and persists a new palette independently of mode', async () => {
    mockMatchMedia(false)
    const user = userEvent.setup()
    renderTheme()

    await user.click(screen.getByRole('button', { name: 'Set twilight palette' }))

    expect(screen.getByTestId('palette')).toHaveTextContent('twilight')
    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('twilight-light')
    expect(localStorage.getItem('medlens.theme.palette')).toBe('twilight')
  })

  it('applies and persists a new mode independently of palette', async () => {
    mockMatchMedia(false)
    const user = userEvent.setup()
    renderTheme()

    await user.click(screen.getByRole('button', { name: 'Set dark' }))

    expect(screen.getByTestId('resolved-mode')).toHaveTextContent('dark')
    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('default-dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('default-dark')
    expect(localStorage.getItem('medlens.theme.mode')).toBe('dark')
  })

  it('switching back to system re-resolves from the current OS preference', async () => {
    mockMatchMedia(true)
    const user = userEvent.setup()
    renderTheme()

    await user.click(screen.getByRole('button', { name: 'Set dark' }))
    expect(screen.getByTestId('resolved-mode')).toHaveTextContent('dark')

    await user.click(screen.getByRole('button', { name: 'Set system' }))

    expect(screen.getByTestId('mode-preference')).toHaveTextContent('system')
    expect(screen.getByTestId('resolved-mode')).toHaveTextContent('dark')
    expect(localStorage.getItem('medlens.theme.mode')).toBe('system')
  })

  it('tracks a live OS preference change while mode is set to system', () => {
    const media = mockMatchMedia(false)
    renderTheme()

    expect(screen.getByTestId('resolved-mode')).toHaveTextContent('light')

    media.fireChange(true)

    expect(screen.getByTestId('resolved-mode')).toHaveTextContent('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('default-dark')
  })

  it('does not react to OS preference changes once an explicit mode is set', async () => {
    const media = mockMatchMedia(false)
    const user = userEvent.setup()
    renderTheme()

    await user.click(screen.getByRole('button', { name: 'Set dark' }))
    media.fireChange(true)

    expect(screen.getByTestId('mode-preference')).toHaveTextContent('dark')
    expect(screen.getByTestId('resolved-mode')).toHaveTextContent('dark')
  })
})
