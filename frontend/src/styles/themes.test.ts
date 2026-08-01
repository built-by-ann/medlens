/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// Read directly off disk rather than `import ... from './themes.css?raw'`:
// this project's Tailwind Vite plugin intercepts every .css import (raw
// query suffix included) to run it through Tailwind's own compiler, which
// returns empty content for a file that's nothing but custom-property
// declarations with no utility classes to generate - there's nothing
// Tailwind-relevant in this file for it to produce. `@types/node` is a
// real devDependency already (just excluded from tsconfig.app.json's
// browser-scoped `types` array), so the reference directive above scopes
// Node's ambient types to only this one test file rather than the whole
// app. This is a plain-text regression check over the source CSS, not a
// rendered component - the guarantee it protects ("Completed" and every
// high/medium/low severity badge look identical no matter which of the 27
// themes is active) is a property of the token *values* themselves, which
// only exist in this file; reading it directly is the only way to assert
// that without spinning up 27 separate rendered pages.
const themesCssPath = join(dirname(fileURLToPath(import.meta.url)), 'themes.css')
const themesCss = readFileSync(themesCssPath, 'utf-8')

const THEME_BLOCK_PATTERN = /:root(\[data-theme='([^']+)'\])?\s*\{([^}]*)\}/g

interface ThemeBlock {
  label: string
  body: string
}

function parseThemeBlocks(): ThemeBlock[] {
  const blocks: ThemeBlock[] = []

  for (const match of themesCss.matchAll(THEME_BLOCK_PATTERN)) {
    blocks.push({ label: match[2] ?? 'default-light', body: match[3] ?? '' })
  }

  return blocks
}

function readToken(body: string, token: string): string {
  const match = body.match(new RegExp(`--${token}:\\s*([^;]+);`))
  if (!match) {
    throw new Error(`Token --${token} not found in block`)
  }
  return match[1] ?? ''
}

describe('themes.css', () => {
  it('defines every theme (9 palettes x 3 modes = 27 blocks minimum)', () => {
    const blocks = parseThemeBlocks()
    expect(blocks.length).toBeGreaterThanOrEqual(27)
  })

  it('gives every badge token (success/warning/danger/info-badge, badge-foreground) the exact same value in every theme', () => {
    const blocks = parseThemeBlocks()
    const badgeTokens = [
      'success-badge',
      'warning-badge',
      'danger-badge',
      'info-badge',
      'badge-foreground',
    ]

    const valueSets = new Set(
      blocks.map((block) => badgeTokens.map((token) => readToken(block.body, token)).join('|')),
    )

    expect(valueSets.size).toBe(1)
  })

  it('gives every plain-text status token (success/warning/danger/info) the exact same value across all themes sharing a mode', () => {
    const blocks = parseThemeBlocks()
    const statusTokens = ['success', 'warning', 'danger', 'info']

    const byMode = new Map<string, Set<string>>()

    for (const block of blocks) {
      const mode = block.label.includes('-')
        ? block.label.split('-').slice(1).join('-')
        : block.label
      const values = statusTokens.map((token) => readToken(block.body, token)).join('|')
      const set = byMode.get(mode) ?? new Set<string>()
      set.add(values)
      byMode.set(mode, set)
    }

    expect(byMode.size).toBeGreaterThan(0)

    for (const [mode, valueSets] of byMode) {
      expect(valueSets.size, `mode "${mode}" has inconsistent status colors across palettes`).toBe(
        1,
      )
    }
  })
})
