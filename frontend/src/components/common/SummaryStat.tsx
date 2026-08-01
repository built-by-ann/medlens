interface SummaryStatProps {
  label: string
  value: string | number
}

export function SummaryStat({ label, value }: SummaryStatProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs font-medium tracking-wide text-muted uppercase">{label}</dt>
      <dd className="text-sm font-semibold break-words text-foreground">{value}</dd>
    </div>
  )
}
