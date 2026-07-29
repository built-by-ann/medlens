import { RecentAnalysisCard } from '@/components/analyses/RecentAnalysisCard'
import type { AnalysisSummary } from '@/types/api'

interface RecentAnalysesListProps {
  analyses: AnalysisSummary[]
  onDelete?: (id: number) => Promise<void>
}

export function RecentAnalysesList({ analyses, onDelete }: RecentAnalysesListProps) {
  return (
    <ul className="flex flex-col gap-4">
      {analyses.map((analysis) => (
        <li key={analysis.id}>
          <RecentAnalysisCard analysis={analysis} onDelete={onDelete} />
        </li>
      ))}
    </ul>
  )
}
