import { Clock, Flame, TrendingDown, Hash } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import {
  formatDate,
  formatDuration,
  LIFECYCLE_LABELS,
  LIFECYCLE_COLORS,
} from '@/lib/utils'
import type { LifecycleSummary, LifecycleStage } from '@/types'

interface LifecyclePanelProps {
  lifecycle: LifecycleSummary
}

export default function LifecyclePanel({ lifecycle }: LifecyclePanelProps) {
  const stages = Object.entries(lifecycle.stage_counts)
    .filter(([, count]) => count > 0)
    .sort(([, a], [, b]) => b - a)

  return (
    <Card>
      <CardHeader>
        <CardTitle>라이프사이클 요약</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Key metrics */}
        <div className="grid grid-cols-2 gap-3">
          <MetricItem
            icon={<Clock className="h-4 w-4 text-lifecycle-origin" />}
            label="최초 발행"
            value={formatDate(lifecycle.origin_time)}
          />
          <MetricItem
            icon={<TrendingDown className="h-4 w-4 text-lifecycle-fadeout" />}
            label="마지막 발행"
            value={formatDate(lifecycle.fadeout_time)}
          />
          <MetricItem
            icon={<Flame className="h-4 w-4 text-lifecycle-explosion" />}
            label="피크 시간"
            value={formatDate(lifecycle.peak_hour)}
          />
          <MetricItem
            icon={<Hash className="h-4 w-4 text-lifecycle-spread" />}
            label="총 기사 수"
            value={`${lifecycle.total_articles}건`}
          />
        </div>

        {/* Duration */}
        {lifecycle.total_duration_hours !== null && (
          <div className="rounded-md bg-secondary/50 px-3 py-2 text-center">
            <span className="text-xs text-muted-foreground">전체 확산 기간</span>
            <p className="text-lg font-semibold text-lifecycle-origin">
              {formatDuration(lifecycle.total_duration_hours)}
            </p>
          </div>
        )}

        {/* Stage distribution */}
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground">단계별 분포</h4>
          {stages.map(([stage, count]) => {
            const pct = lifecycle.total_articles > 0 ? (count / lifecycle.total_articles) * 100 : 0
            return (
              <div key={stage} className="flex items-center gap-2">
                <Badge stage={stage as LifecycleStage}>
                  {LIFECYCLE_LABELS[stage as LifecycleStage]}
                </Badge>
                <div className="flex-1">
                  <div className="h-1.5 w-full rounded-full bg-secondary">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${pct}%`,
                        backgroundColor: LIFECYCLE_COLORS[stage as LifecycleStage],
                      }}
                    />
                  </div>
                </div>
                <span className="text-xs tabular-nums text-muted-foreground">
                  {count}
                </span>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

function MetricItem({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: string
}) {
  return (
    <div className="flex items-start gap-2 rounded-md bg-secondary/30 p-2">
      <div className="mt-0.5">{icon}</div>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-sm font-medium">{value}</p>
      </div>
    </div>
  )
}
