import { PageHeader } from '@/components/common/PageHeader'
import { Card } from '@/components/common/Card'

// Update these to point at your own fork/deployment.
const GITHUB_URL = 'https://github.com/built-by-ann/medlens'
const LIVE_DEMO_URL = 'http://medlenshealth.com'

export function AboutPage() {
  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="About MedLens"
        description="An AI-assisted medication reconciliation demonstration, inspired by clinical informatics research."
        actions={
          <>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="cursor-pointer rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
            >
              GitHub Repository
            </a>
            <a
              href={LIVE_DEMO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
            >
              Live Demo
            </a>
          </>
        }
      />

      <div className="flex flex-col gap-6">
        <Card className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold text-foreground">Where it started</h2>
          <p className="text-sm text-muted">
            The idea for MedLens started during a Biomedical Informatics internship at Vanderbilt
            University Medical Center, working on a study that reviewed more than 37,000 patient
            encounters. In my research, I discovered through analysis of 37,000 patient encounters
            and conversations with providers from various specialties that the same medication could
            be described differently across a patient&apos;s own notes: discontinued in one place,
            still listed as active in another.
          </p>
          <p className="text-sm text-muted">
            That project was research that allowed me to identify that the issue exists, not a
            software solution. MedLens is a separate, personal project built afterward to explore
            whether an AI-assisted pipeline could help surface that kind of inconsistency for a
            human to review. It isn&apos;t a continuation of that research, and it wasn&apos;t built
            for real patient care.
          </p>
        </Card>

        <Card className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold text-foreground">
            What is medication reconciliation?
          </h2>
          <p className="text-sm text-muted">
            It&apos;s the process of checking that a patient&apos;s medication list agrees with what
            their clinical notes actually say. In practice, a chart is written by different people
            at different times for different purposes, so mismatches creep in: a medication
            discontinued in one place but still active elsewhere, a dosage that was updated in only
            one place, or a medication list that&apos;s simply missing something a recent visit note
            mentions.
          </p>
        </Card>

        <Card className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold text-foreground">How MedLens helps</h2>
          <p className="text-sm text-muted">
            Upload a patient&apos;s clinical documents, and MedLens reads them, extracts the
            medications mentioned, and compares them against the patient&apos;s medication list.
            Anything that doesn&apos;t line up is presented as a finding, with the source text
            behind it, for a provider to review.
          </p>
        </Card>

        <Card className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold text-foreground">Learn more</h2>
          <p className="text-sm text-muted">
            This page tells the story behind MedLens. For the source code, architecture, and
            deployment details, see the{' '}
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-link hover:underline"
            >
              GitHub repository
            </a>
            .
          </p>
        </Card>

        <Card className="flex flex-col gap-1 border-l-4 border-l-warning">
          <h2 className="text-sm font-semibold text-foreground">
            Educational project, not a clinical tool
          </h2>
          <p className="text-sm text-muted">
            MedLens uses synthetic clinical data only. It is not intended for clinical use and
            should not be used for real medical decision-making.
          </p>
        </Card>
      </div>
    </div>
  )
}
