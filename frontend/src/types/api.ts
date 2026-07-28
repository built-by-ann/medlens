/**
 * Frontend representations of backend response models.
 *
 * These mirror the Pydantic response schemas documented in docs/api.md and
 * are added to incrementally as each backend resource is wired up on the
 * frontend. They intentionally do not cover every backend model yet.
 */

export interface User {
  id: number
  email: string
  name: string | null
  created_at: string
}
