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
