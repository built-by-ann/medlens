import { RecentAnalysisCard } from '@/components/dashboard/RecentAnalysisCard'
import type { AnalysisSummary } from '@/types/api'

interface RecentAnalysesListProps {
  analyses: AnalysisSummary[]
}

export function RecentAnalysesList({ analyses }: RecentAnalysesListProps) {
  return (
    <ul className="flex flex-col gap-4">
      {analyses.map((analysis) => (
        <li key={analysis.id}>
          <RecentAnalysisCard analysis={analysis} />
        </li>
      ))}
    </ul>
  )
}
