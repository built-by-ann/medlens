import { Card } from '@/components/common/Card'
import { SummaryStat } from '@/components/common/SummaryStat'
import { DiscrepancySeverityBadge } from '@/components/analyses/DiscrepancySeverityBadge'
import { ResolutionStatusBadge } from '@/components/analyses/ResolutionStatusBadge'
import { documentTypeLabel } from '@/api/clinicalDocuments'
import { discrepancyTypeLabel } from '@/utils/discrepancy'
import { cn } from '@/utils/cn'
import type { MedicationDiscrepancy } from '@/types/api'

// A left border repeats the same severity signal as the badge, so severity
// is never communicated by color alone. Uses the same fixed *-badge tokens
// as DiscrepancySeverityBadge (not the theme-varying danger/warning used
// for plain text elsewhere) so the stripe is the exact same color as the
// pill it echoes, in every theme - see docs/frontend.md.
const SEVERITY_BORDER_STYLES: Record<MedicationDiscrepancy['severity'], string> = {
  high: 'border-l-4 border-l-danger-badge',
  medium: 'border-l-4 border-l-warning-badge',
  low: 'border-l-4 border-l-border',
}

interface MedicationDiscrepancyCardProps {
  discrepancy: MedicationDiscrepancy
}

export function MedicationDiscrepancyCard({ discrepancy }: MedicationDiscrepancyCardProps) {
  const medicationName =
    discrepancy.medication?.medication_name ??
    discrepancy.medication_mention?.medication_name ??
    'Unknown medication'

  return (
    <Card className={cn('flex flex-col gap-3', SEVERITY_BORDER_STYLES[discrepancy.severity])}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 className="text-sm font-semibold break-words text-foreground">{medicationName}</h4>
          <p className="text-xs text-muted">{discrepancyTypeLabel(discrepancy.discrepancy_type)}</p>
        </div>
        <div className="flex flex-wrap items-start gap-2">
          <DiscrepancySeverityBadge severity={discrepancy.severity} />
          <ResolutionStatusBadge status={discrepancy.resolution_status} />
        </div>
      </div>

      {discrepancy.ai_explanation && (
        <p className="text-sm break-words text-foreground">{discrepancy.ai_explanation}</p>
      )}

      {(discrepancy.expected_value || discrepancy.observed_value) && (
        <dl className="grid grid-cols-2 gap-4">
          {discrepancy.expected_value && (
            <SummaryStat label="Expected" value={discrepancy.expected_value} />
          )}
          {discrepancy.observed_value && (
            <SummaryStat label="Observed" value={discrepancy.observed_value} />
          )}
        </dl>
      )}

      {discrepancy.recommendation && (
        <p className="text-sm break-words text-muted">
          <span className="font-medium">Recommendation: </span>
          {discrepancy.recommendation}
        </p>
      )}

      <div className="border-t border-border pt-3">
        <h5 className="text-xs font-medium tracking-wide text-muted uppercase">
          Supporting evidence
        </h5>

        {discrepancy.medication_mention ? (
          <div className="mt-2 flex flex-col gap-1 rounded-md bg-background p-3">
            <p className="text-xs break-words text-muted">
              Source: {discrepancy.medication_mention.clinical_document.title} (
              {documentTypeLabel(discrepancy.medication_mention.clinical_document.document_type)})
            </p>
            {discrepancy.medication_mention.context_text && (
              <p className="text-sm break-words whitespace-pre-wrap text-foreground">
                &ldquo;{discrepancy.medication_mention.context_text}&rdquo;
              </p>
            )}
          </div>
        ) : discrepancy.medication ? (
          <p className="mt-2 text-sm break-words text-muted">
            Currently on the medication list: {discrepancy.medication.medication_name},{' '}
            {discrepancy.medication.dose}, {discrepancy.medication.route},{' '}
            {discrepancy.medication.frequency} ({discrepancy.medication.status}).
          </p>
        ) : (
          <p className="mt-2 text-sm text-muted">
            No supporting evidence was recorded for this finding.
          </p>
        )}
      </div>
    </Card>
  )
}
