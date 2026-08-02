import { Link } from 'react-router-dom'
import { Card } from '@/components/common/Card'
import { ROUTES } from '@/routes/paths'

const STEPS = [
  {
    number: '1',
    title: 'Upload documents',
    description: 'Paste text or upload visit notes, discharge summaries, and medication lists.',
  },
  {
    number: '2',
    title: 'AI extracts medications',
    description: 'Structured medication details are pulled from each document automatically.',
  },
  {
    number: '3',
    title: 'Reconciliation compares sources',
    description: "A deterministic engine checks what's extracted against the patient's record.",
  },
  {
    number: '4',
    title: 'Review evidence-backed findings',
    description: 'Every discrepancy links back to the exact document and text it came from.',
  },
]

const HIGHLIGHTS = [
  {
    title: 'Built for review, not blind trust',
    description: 'AI extracts and suggests; a deterministic engine and a human reviewer decide.',
  },
  {
    title: 'Evidence, not just a verdict',
    description: 'Every finding cites its source document and severity, so you can check the work.',
  },
  {
    title: 'Multiple documents, one patient',
    description: 'Visit notes, discharge summaries, and medication lists reconciled together.',
  },
]

export function HomePage() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-16 px-4 py-16 sm:px-6">
      <section className="flex flex-col items-start gap-5">
        <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
          MedLens
        </h1>
        <p className="max-w-2xl text-lg text-muted">
          AI-powered medication reconciliation for clinical documentation. Upload notes, and MedLens
          finds where they disagree - with the evidence to back it up.
        </p>
        <div className="flex flex-wrap gap-3 pt-2">
          <Link
            to={ROUTES.signup}
            className="cursor-pointer rounded-md bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
          >
            Sign up
          </Link>
          <Link
            to={ROUTES.login}
            className="cursor-pointer rounded-md border border-border px-5 py-2.5 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
          >
            Log in
          </Link>
        </div>
      </section>

      <section aria-labelledby="how-it-works-heading" className="flex flex-col gap-6">
        <h2 id="how-it-works-heading" className="text-lg font-semibold text-foreground">
          How it works
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step) => (
            <Card key={step.number} className="flex flex-col gap-2">
              <span className="text-xs font-medium tracking-wide text-muted uppercase">
                Step {step.number}
              </span>
              <h3 className="text-sm font-semibold text-foreground">{step.title}</h3>
              <p className="text-sm text-muted">{step.description}</p>
            </Card>
          ))}
        </div>
      </section>

      <section aria-labelledby="highlights-heading" className="flex flex-col gap-6">
        <h2 id="highlights-heading" className="text-lg font-semibold text-foreground">
          Why it's built this way
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {HIGHLIGHTS.map((item) => (
            <div key={item.title} className="flex flex-col gap-1">
              <h3 className="text-sm font-semibold text-foreground">{item.title}</h3>
              <p className="text-sm text-muted">{item.description}</p>
            </div>
          ))}
        </div>
      </section>

      <p className="max-w-2xl text-xs text-muted">
        MedLens uses synthetic clinical data only and is intended for educational and portfolio
        purposes - not for use with real patient information.
      </p>
    </div>
  )
}
