import { Card } from '@/components/common/Card'
import { cn } from '@/utils/cn'
import { useTheme } from '@/hooks/useTheme'
import { MODE_OPTIONS, PALETTE_OPTIONS } from '@/contexts/ThemeContext'
import type { Mode, PaletteName } from '@/lib/themeStorage'

// Static preview swatches for the palette picker below, one per (palette,
// mode) combination, so a card always shows what selecting it would
// actually look like in whichever mode is currently active. These
// intentionally duplicate real values from src/styles/themes.css rather
// than reading the live CSS variables: the whole point of a picker is
// comparing every option side by side, including palettes that are not
// currently applied, so this is the one deliberate exception to
// "components consume semantic tokens, never raw colors" elsewhere in the
// app (see docs/frontend.md's Theme Architecture section). Keep this table
// in sync by hand if themes.css's values ever change.
const PALETTE_PREVIEWS: Record<
  PaletteName,
  Record<Mode, { background: string; surface: string; primary: string; secondary: string }>
> = {
  default: {
    light: { background: '#f8fafc', surface: '#ffffff', primary: '#2563eb', secondary: '#475569' },
    dark: { background: '#0f172a', surface: '#1e293b', primary: '#2563eb', secondary: '#475569' },
    'high-contrast': {
      background: '#ffffff',
      surface: '#ffffff',
      primary: '#0a3fa3',
      secondary: '#3f3f46',
    },
  },
  blossom: {
    light: { background: '#fbf4ee', surface: '#ffffff', primary: '#8a6423', secondary: '#8a3c26' },
    dark: { background: '#1c120d', surface: '#2b1d16', primary: '#e8c377', secondary: '#d98f63' },
    'high-contrast': {
      background: '#ffffff',
      surface: '#ffffff',
      primary: '#6b4f14',
      secondary: '#7a2e1c',
    },
  },
  sage: {
    light: { background: '#ede7da', surface: '#fbf9f3', primary: '#55613f', secondary: '#4f7a63' },
    dark: { background: '#12160f', surface: '#1d231a', primary: '#9cb37e', secondary: '#7fb39c' },
    'high-contrast': {
      background: '#ffffff',
      surface: '#ffffff',
      primary: '#3e4f2a',
      secondary: '#1f5a48',
    },
  },
  twilight: {
    light: { background: '#eef1f9', surface: '#ffffff', primary: '#294a8f', secondary: '#5b5fa8' },
    dark: { background: '#0a111a', surface: '#141e2e', primary: '#3e63b0', secondary: '#4c699c' },
    'high-contrast': {
      background: '#ffffff',
      surface: '#ffffff',
      primary: '#294a8f',
      secondary: '#4a3e70',
    },
  },
  terracotta: {
    light: { background: '#f7e6dd', surface: '#ffffff', primary: '#863525', secondary: '#b65a28' },
    dark: { background: '#271525', surface: '#3a2420', primary: '#f9a45f', secondary: '#dd733c' },
    'high-contrast': {
      background: '#ffffff',
      surface: '#ffffff',
      primary: '#863525',
      secondary: '#8c3d12',
    },
  },
  coastal: {
    light: { background: '#f2edf1', surface: '#ffffff', primary: '#14746e', secondary: '#593e58' },
    dark: { background: '#1b1420', surface: '#2a1f2e', primary: '#4fc2da', secondary: '#f0a0b4' },
    'high-contrast': {
      background: '#ffffff',
      surface: '#ffffff',
      primary: '#0e5c58',
      secondary: '#452e44',
    },
  },
  lavender: {
    light: { background: '#f3e9e1', surface: '#ffffff', primary: '#4a4f87', secondary: '#6f6390' },
    dark: { background: '#171426', surface: '#221d34', primary: '#7b81c4', secondary: '#e5a9b1' },
    'high-contrast': {
      background: '#ffffff',
      surface: '#ffffff',
      primary: '#363b70',
      secondary: '#7a2e3d',
    },
  },
  aurora: {
    light: { background: '#f8f4fa', surface: '#ffffff', primary: '#2e68bb', secondary: '#af28aa' },
    dark: { background: '#12101f', surface: '#1d1a30', primary: '#5a8fd9', secondary: '#d65ecf' },
    'high-contrast': {
      background: '#ffffff',
      surface: '#ffffff',
      primary: '#1c3f73',
      secondary: '#6e1a6b',
    },
  },
  botanical: {
    light: { background: '#faf7f5', surface: '#ffffff', primary: '#8b263e', secondary: '#786825' },
    dark: { background: '#1a0e12', surface: '#2a1820', primary: '#d9607a', secondary: '#c3a93f' },
    'high-contrast': {
      background: '#ffffff',
      surface: '#ffffff',
      primary: '#6e1e31',
      secondary: '#4a3f16',
    },
  },
}

export function AppearanceSettings() {
  const { palette, modePreference, resolvedMode, setPalette, setModePreference } = useTheme()

  return (
    <Card className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold text-foreground">Appearance</h2>
        <p className="mt-1 text-sm text-muted">
          Choose a color palette, then a light, dark, or high-contrast rendering of it. Changes
          apply immediately and are remembered on this device.
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium text-foreground">Palette</span>
        <div
          role="group"
          aria-label="Palette"
          className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
        >
          {PALETTE_OPTIONS.map((option) => {
            const preview = PALETTE_PREVIEWS[option.value][resolvedMode]
            const isActive = palette === option.value

            return (
              <button
                key={option.value}
                type="button"
                aria-pressed={isActive}
                onClick={() => setPalette(option.value)}
                className={cn(
                  'flex cursor-pointer flex-col gap-2 rounded-lg border p-3 text-left',
                  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
                  isActive ? 'border-primary' : 'border-border hover:bg-surface-hover',
                )}
              >
                <span
                  aria-hidden="true"
                  className="flex h-8 overflow-hidden rounded"
                  style={{ backgroundColor: preview.background }}
                >
                  <span className="h-full w-1/3" style={{ backgroundColor: preview.surface }} />
                  <span className="h-full w-1/3" style={{ backgroundColor: preview.primary }} />
                  <span className="h-full w-1/3" style={{ backgroundColor: preview.secondary }} />
                </span>
                <span className="text-sm font-medium text-foreground">{option.label}</span>
                <span className="text-xs text-muted">{option.description}</span>
              </button>
            )
          })}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium text-foreground">Mode</span>
        <div
          role="group"
          aria-label="Mode"
          className="inline-flex w-fit flex-wrap rounded-md border border-border p-1"
        >
          {MODE_OPTIONS.map((option) => {
            const isActive = modePreference === option.value

            return (
              <button
                key={option.value}
                type="button"
                aria-pressed={isActive}
                onClick={() => setModePreference(option.value)}
                title={option.description}
                className={cn(
                  'cursor-pointer rounded px-3 py-1.5 text-sm font-medium',
                  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted hover:bg-surface-hover',
                )}
              >
                {option.label}
              </button>
            )
          })}
          <button
            type="button"
            aria-pressed={modePreference === 'system'}
            onClick={() => setModePreference('system')}
            title="Match your operating system's light/dark setting"
            className={cn(
              'cursor-pointer rounded px-3 py-1.5 text-sm font-medium',
              'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
              modePreference === 'system'
                ? 'bg-primary text-primary-foreground'
                : 'text-muted hover:bg-surface-hover',
            )}
          >
            System
          </button>
        </div>
        {modePreference === 'system' && (
          <p className="text-xs text-muted">
            Currently using {resolvedMode === 'dark' ? 'Dark' : 'Light'} to match your system.
          </p>
        )}
      </div>
    </Card>
  )
}
