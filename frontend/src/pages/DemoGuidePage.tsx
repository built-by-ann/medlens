import { PageHeader } from '@/components/common/PageHeader'
import { Card } from '@/components/common/Card'
import { DemoPatientCard } from '@/components/demo/DemoPatientCard'
import { DEMO_PATIENTS } from '@/components/demo/demoPatients'

const GETTING_STARTED_STEPS = [
  {
    number: '1',
    title: 'Create a patient',
    description: 'Add one of the demo patients below, or use your own name.',
  },
  {
    number: '2',
    title: 'Add the medication list',
    description: 'Import the medications.csv from a demo dataset, or enter medications by hand.',
  },
  {
    number: '3',
    title: 'Upload clinical documents',
    description: 'Upload the included visit notes, discharge summary, and reconciliation form.',
  },
  {
    number: '4',
    title: 'Run an analysis',
    description: 'Select the uploaded documents and create an analysis.',
  },
  {
    number: '5',
    title: 'Review discrepancies',
    description: 'See what MedLens found, grouped by severity, with the evidence behind each one.',
  },
  {
    number: '6',
    title: 'Resolve discrepancies',
    description: 'Accept, update, or dismiss each finding. Entirely optional.',
  },
]

const TIPS = [
  'Upload multiple documents for the same patient. A single note rarely tells the whole story.',
  'Documents from different encounters produce richer analyses than one long note.',
  'Importing a medication list from CSV is faster than entering medications one at a time.',
  'Different document types can legitimately conflict. That tension is what MedLens is built to surface.',
  'Each demo dataset below was written to produce specific, predictable findings. See "Expected findings" on each one before you start.',
]

export function DemoGuidePage() {
  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Demo Guide"
        description="Everything you need to explore MedLens with realistic synthetic patient cases. Follow the steps below from top to bottom, then pick a demo patient to download."
      />

      <section aria-labelledby="getting-started-heading" className="flex flex-col gap-4">
        <h2 id="getting-started-heading" className="text-lg font-semibold text-foreground">
          Getting started
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {GETTING_STARTED_STEPS.map((step) => (
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

      <section aria-labelledby="tips-heading" className="flex flex-col gap-4">
        <h2 id="tips-heading" className="text-lg font-semibold text-foreground">
          Tips for the best experience
        </h2>
        <Card>
          <ul className="list-disc space-y-2 pl-5 text-sm text-muted">
            {TIPS.map((tip) => (
              <li key={tip}>{tip}</li>
            ))}
          </ul>
        </Card>
      </section>

      <section aria-labelledby="demo-patients-heading" className="flex flex-col gap-4">
        <h2 id="demo-patients-heading" className="text-lg font-semibold text-foreground">
          Demo patients
        </h2>
        <p className="text-sm text-muted">
          Four synthetic cases, each with a medication list and a set of clinical documents written
          to produce specific, reviewable findings. Expand a case to see what to expect and download
          everything as one file.
        </p>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {DEMO_PATIENTS.map((patient) => (
            <DemoPatientCard key={patient.slug} patient={patient} />
          ))}
        </div>
      </section>
    </div>
  )
}
