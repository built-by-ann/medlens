import { useState } from 'react'
import { Card } from '@/components/common/Card'
import type { DemoPatient } from '@/components/demo/demoPatients'

interface DemoPatientCardProps {
  patient: DemoPatient
}

export function DemoPatientCard({ patient }: DemoPatientCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const contentId = `demo-patient-${patient.slug}`

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <span className="text-xs font-medium tracking-wide text-muted uppercase">
          {patient.caseType}
        </span>
        <h3 className="text-base font-semibold text-foreground">
          {patient.name}, {patient.age}
        </h3>
        <p className="text-sm text-muted">{patient.history}</p>
        <p className="text-sm text-foreground">{patient.highlight}</p>
      </div>

      <button
        type="button"
        onClick={() => setIsExpanded((current) => !current)}
        aria-expanded={isExpanded}
        aria-controls={contentId}
        className="cursor-pointer self-start rounded-md px-2 py-1 text-sm font-medium text-link hover:bg-primary/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
      >
        {isExpanded ? 'Hide case details' : 'View case details'}
      </button>

      {isExpanded && (
        <div id={contentId} className="flex flex-col gap-3 rounded-md bg-background p-4">
          <div>
            <h4 className="text-sm font-semibold text-foreground">Expected findings</h4>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted">
              {patient.expectedFindings.map((finding) => (
                <li key={finding}>{finding}</li>
              ))}
            </ul>
          </div>

          <p className="text-xs text-muted">
            Includes a medication list and {patient.fileCount - 1} clinical documents, plus a README
            with the recommended upload order.
          </p>

          <a
            href={patient.downloadUrl}
            download
            className="cursor-pointer self-start rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
          >
            Download complete dataset
          </a>
        </div>
      )}
    </Card>
  )
}
