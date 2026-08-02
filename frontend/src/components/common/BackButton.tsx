import { useNavigate } from 'react-router-dom'

interface BackButtonProps {
  /** Route this button always navigates to. */
  to: string
  /** Named after the destination, not the action: renders as "Back to {label}". */
  label: string
}

/**
 * A single "Back to {label}" control shared by every patient-related page,
 * so navigation doesn't get hardcoded independently on each one.
 *
 * Always navigates to the given logical-parent route (`to`). An earlier
 * version preferred real browser-history back navigation (`navigate(-1)`)
 * so the user would land exactly where they came from, but that meant the
 * actual destination depended on this session's in-app navigation path,
 * while the visible label always named the fixed logical parent - the two
 * silently disagreed whenever a user's path diverged from a straight
 * drill-down (e.g. Overview -> Documents -> "View Patient" back to
 * Overview -> clicking "Back to Patients" here actually landed back on
 * Documents, since that was the real previous history entry). Always
 * honoring `to` keeps the label truthful on every click, independent of
 * how the page was reached.
 */
export function BackButton({ to, label }: BackButtonProps) {
  const navigate = useNavigate()

  return (
    <button
      type="button"
      onClick={() => navigate(to)}
      className="self-start text-sm text-link hover:underline"
    >
      <span aria-hidden="true">←</span> Back to {label}
    </button>
  )
}
