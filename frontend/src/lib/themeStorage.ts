const PALETTE_STORAGE_KEY = 'medlens.theme.palette'
const MODE_STORAGE_KEY = 'medlens.theme.mode'

// A palette is the color family; a mode is which of its three renderings is
// active. Every palette supports all three modes (see src/styles/themes.css)
// - 'default' is the application's own original look, the rest are drawn
// from the provided inspiration palettes (see docs/frontend.md's Theme
// Architecture section for the full color derivation of each).
export const PALETTE_NAMES = [
  'default',
  'blossom',
  'sage',
  'twilight',
  'terracotta',
  'coastal',
  'lavender',
  'aurora',
  'botanical',
] as const

export type PaletteName = (typeof PALETTE_NAMES)[number]

// 'system' is a stored preference meaning "resolve light/dark from the OS
// setting" - it never resolves to 'high-contrast', since there is no
// light/dark-style OS signal for that; it's always an explicit choice.
export const MODE_NAMES = ['light', 'dark', 'high-contrast'] as const

export type Mode = (typeof MODE_NAMES)[number]
export type ModePreference = Mode | 'system'

// The actual value written to `data-theme` on <html> - see themes.css.
export type ThemeName = `${PaletteName}-${Mode}`

const VALID_PALETTES = new Set<string>(PALETTE_NAMES)
const VALID_MODES = new Set<string>([...MODE_NAMES, 'system'])

function isPaletteName(value: string): value is PaletteName {
  return VALID_PALETTES.has(value)
}

function isModePreference(value: string): value is ModePreference {
  return VALID_MODES.has(value)
}

export function getStoredPalette(): PaletteName | null {
  const stored = localStorage.getItem(PALETTE_STORAGE_KEY)
  return stored && isPaletteName(stored) ? stored : null
}

export function setStoredPalette(palette: PaletteName): void {
  localStorage.setItem(PALETTE_STORAGE_KEY, palette)
}

export function getStoredMode(): ModePreference | null {
  const stored = localStorage.getItem(MODE_STORAGE_KEY)
  return stored && isModePreference(stored) ? stored : null
}

export function setStoredMode(mode: ModePreference): void {
  localStorage.setItem(MODE_STORAGE_KEY, mode)
}

export function clearStoredTheme(): void {
  localStorage.removeItem(PALETTE_STORAGE_KEY)
  localStorage.removeItem(MODE_STORAGE_KEY)
}
