import { createContext } from 'react'
import type { Mode, ModePreference, PaletteName, ThemeName } from '@/lib/themeStorage'

export interface PaletteOption {
  value: PaletteName
  label: string
  description: string
}

// Ordered for display in the Appearance section's palette picker - Default
// first as the application's own original look, then the 6 palettes drawn
// from the provided inspiration boards (see docs/frontend.md's Theme
// Architecture section for how each was derived).
export const PALETTE_OPTIONS: PaletteOption[] = [
  { value: 'default', label: 'Default', description: "MedLens's original look." },
  { value: 'blossom', label: 'Blossom', description: 'Elegant, warm, and soft.' },
  { value: 'sage', label: 'Sage', description: 'Calm, natural, and minimal.' },
  { value: 'twilight', label: 'Twilight', description: 'Modern and calm.' },
  { value: 'terracotta', label: 'Terracotta', description: 'Warm, confident, and editorial.' },
  { value: 'coastal', label: 'Coastal', description: 'Fresh, modern, and creative.' },
  { value: 'lavender', label: 'Lavender', description: 'Relaxed, friendly, and soft.' },
  { value: 'aurora', label: 'Aurora', description: 'Vibrant, energetic, and creative.' },
  { value: 'botanical', label: 'Botanical', description: 'Rose and olive garden tones.' },
]

export interface ModeOption {
  value: Mode
  label: string
  description: string
}

export const MODE_OPTIONS: ModeOption[] = [
  { value: 'light', label: 'Light', description: 'Bright background, dark text.' },
  { value: 'dark', label: 'Dark', description: 'Dark background, light text.' },
  {
    value: 'high-contrast',
    label: 'High Contrast',
    description: 'Black and white with maximum readability. Aims for AAA contrast.',
  },
]

export interface ThemeContextValue {
  // The selected color family, independent of mode.
  palette: PaletteName
  // The user's stored mode preference: one of the 3 real modes, or 'system'.
  modePreference: ModePreference
  // 'system' resolved to 'light' or 'dark'; otherwise identical to
  // modePreference. Never 'system' itself.
  resolvedMode: Mode
  // `${palette}-${resolvedMode}` - the actual value applied to `data-theme`.
  resolvedTheme: ThemeName
  setPalette: (palette: PaletteName) => void
  setModePreference: (mode: ModePreference) => void
}

export const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)
