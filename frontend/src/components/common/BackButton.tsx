import { useLocation, useNavigate } from 'react-router-dom'

interface BackButtonProps {
  /** Logical parent route to fall back to when there's no in-app history to return to. */
  to: string
  /** Named after the destination, not the action: renders as "Back to {label}". */
  label: string
}

/**
 * A single "Back to {label}" control shared by every patient-related page,
 * so navigation doesn't get hardcoded independently on each one.
 *
 * Prefers real browser back navigation (`navigate(-1)`) so the user lands
 * exactly where they came from, but falls back to the logical parent route
 * (`to`) when there's nothing to go back to - most notably a direct link or
 * a fresh page load, where a `-1` would leave the app entirely. React
 * Router assigns the location key "default" only to that initial entry, so
 * checking for it is how this distinguishes "arrived via in-app navigation"
 * from "arrived from outside" without needing real `window.history` depth,
 * which isn't reliably readable from script.
 */
export function BackButton({ to, label }: BackButtonProps) {
  const navigate = useNavigate()
  const location = useLocation()

  function handleClick() {
    if (location.key === 'default') {
      navigate(to)
    } else {
      navigate(-1)
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className="self-start text-sm text-slate-600 hover:underline"
    >
      <span aria-hidden="true">←</span> Back to {label}
    </button>
  )
}
