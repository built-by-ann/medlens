import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'

// React Testing Library's automatic per-test cleanup relies on detecting a
// global afterEach; since test.globals is deliberately off (explicit
// imports, matching the rest of this codebase), it is wired up by hand
// here instead, once, rather than repeated in every test file.
afterEach(() => {
  cleanup()
})

// jsdom does not implement HTMLDialogElement's imperative modal behavior
// (showModal/close, or Escape triggering a cancel event); this is a
// documented jsdom limitation, not a gap in application code. Real browsers
// already implement all of this natively; this polyfill only exists so
// components built on the real <dialog> element are testable here.
// jsdom does not implement window.matchMedia at all; this is, again, a
// jsdom limitation rather than an application gap. Default to "no
// preference matched" (light); ThemeProvider's system-preference tests
// override this per test via vi.stubGlobal to simulate a dark OS setting.
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia
}

if (typeof HTMLDialogElement !== 'undefined' && !HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }

  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.open) return
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return

    const openDialogs = document.querySelectorAll('dialog[open]')
    const topDialog = openDialogs[openDialogs.length - 1] as HTMLDialogElement | undefined

    if (!topDialog) return

    const cancelEvent = new Event('cancel', { cancelable: true })
    const notPrevented = topDialog.dispatchEvent(cancelEvent)

    if (notPrevented) {
      topDialog.close()
    }
  })
}
