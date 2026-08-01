import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { AppearanceSettings } from '@/components/settings/AppearanceSettings'
import { ThemeProvider } from '@/contexts/ThemeProvider'

function renderAppearance() {
  return render(
    <ThemeProvider>
      <AppearanceSettings />
    </ThemeProvider>,
  )
}

describe('AppearanceSettings', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
  })

  it('shows all 9 palettes as options', () => {
    renderAppearance()
    const paletteGroup = within(screen.getByRole('group', { name: 'Palette' }))

    for (const name of [
      'Default',
      'Blossom',
      'Sage',
      'Twilight',
      'Terracotta',
      'Coastal',
      'Lavender',
      'Aurora',
      'Botanical',
    ]) {
      expect(paletteGroup.getByRole('button', { name: new RegExp(`^${name}`) })).toBeInTheDocument()
    }
  })

  it('shows Light, Dark, High Contrast, and System as mode options', () => {
    renderAppearance()
    const modeGroup = within(screen.getByRole('group', { name: 'Mode' }))

    expect(modeGroup.getByRole('button', { name: 'Light' })).toBeInTheDocument()
    expect(modeGroup.getByRole('button', { name: 'Dark' })).toBeInTheDocument()
    expect(modeGroup.getByRole('button', { name: 'High Contrast' })).toBeInTheDocument()
    expect(modeGroup.getByRole('button', { name: 'System' })).toBeInTheDocument()
  })

  it('marks Default palette and System mode as pressed by default', () => {
    renderAppearance()
    const paletteGroup = within(screen.getByRole('group', { name: 'Palette' }))
    const modeGroup = within(screen.getByRole('group', { name: 'Mode' }))

    expect(paletteGroup.getByRole('button', { name: /^Default/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(modeGroup.getByRole('button', { name: 'System' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(document.documentElement.getAttribute('data-theme')).toBe('default-light')
  })

  it('selecting a palette applies it immediately without changing the current mode', async () => {
    const user = userEvent.setup()
    renderAppearance()
    const paletteGroup = within(screen.getByRole('group', { name: 'Palette' }))
    const modeGroup = within(screen.getByRole('group', { name: 'Mode' }))

    await user.click(modeGroup.getByRole('button', { name: 'Dark' }))
    await user.click(paletteGroup.getByRole('button', { name: /^Twilight/ }))

    expect(document.documentElement.getAttribute('data-theme')).toBe('twilight-dark')
    expect(paletteGroup.getByRole('button', { name: /^Twilight/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('selecting a mode applies it immediately without changing the current palette', async () => {
    const user = userEvent.setup()
    renderAppearance()
    const paletteGroup = within(screen.getByRole('group', { name: 'Palette' }))
    const modeGroup = within(screen.getByRole('group', { name: 'Mode' }))

    await user.click(paletteGroup.getByRole('button', { name: /^Sage/ }))
    await user.click(modeGroup.getByRole('button', { name: 'High Contrast' }))

    expect(document.documentElement.getAttribute('data-theme')).toBe('sage-high-contrast')
    expect(modeGroup.getByRole('button', { name: 'High Contrast' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('persists both the selected palette and mode to localStorage', async () => {
    const user = userEvent.setup()
    renderAppearance()
    const paletteGroup = within(screen.getByRole('group', { name: 'Palette' }))
    const modeGroup = within(screen.getByRole('group', { name: 'Mode' }))

    await user.click(paletteGroup.getByRole('button', { name: /^Coastal/ }))
    await user.click(modeGroup.getByRole('button', { name: 'Dark' }))

    expect(localStorage.getItem('medlens.theme.palette')).toBe('coastal')
    expect(localStorage.getItem('medlens.theme.mode')).toBe('dark')
  })
})
