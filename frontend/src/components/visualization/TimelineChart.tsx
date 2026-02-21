import { useMemo } from 'react'
import { ExternalLink, Zap } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { LIFECYCLE_COLORS, LIFECYCLE_LABELS, formatDate } from '@/lib/utils'
import type { TimelineItem, ExplosionPoint, LifecycleStage } from '@/types'

interface TimelineChartProps {
  items: TimelineItem[]
  explosions: ExplosionPoint[]
}

export default function TimelineChart({ items, explosions }: TimelineChartProps) {
  // Sort items: origin first, then by published_at ascending
  const sorted = useMemo(
    () => [...items].sort((a, b) => {
      if (a.is_origin && !b.is_origin) return -1
      if (!a.is_origin && b.is_origin) return 1
      return new Date(a.published_at).getTime() - new Date(b.published_at).getTime()
    }),
    [items],
  )

  // Build explosion time ranges for quick lookup
  const explosionRanges = useMemo(
    () =>
      explosions.map((e) => ({
        start: new Date(e.start_time).getTime(),
        end: new Date(e.end_time).getTime(),
        count: e.peak_count,
      })),
    [explosions],
  )

  if (items.length === 0) {
    return (
      <div className="flex h-96 items-center justify-center text-muted-foreground">
        타임라인 데이터가 없습니다.
      </div>
    )
  }

  // Check if an item falls within an explosion zone
  function isInExplosion(publishedAt: string) {
    const t = new Date(publishedAt).getTime()
    return explosionRanges.some((r) => t >= r.start && t <= r.end)
  }

  // Group consecutive explosion items to show a single marker
  let lastExplosionShown = -1

  return (
    <div
      className="max-h-[400px] sm:max-h-[600px] overflow-x-hidden overflow-y-auto px-1 py-4 sm:px-2"
      role="img"
      aria-label={`${items.length}개 기사의 타임라인. ${explosions.length}개의 폭발 구간 포함.`}
      style={{ touchAction: 'pan-y' }}
    >
      <div className="relative ml-2 border-l-2 border-border pl-4 sm:ml-4 sm:pl-6">
        {sorted.map((item) => {
          const inExplosion = isInExplosion(item.published_at)
          const stage = item.lifecycle_stage as LifecycleStage
          const color = LIFECYCLE_COLORS[stage] || '#6b7280'

          // Show explosion marker before the first item in each explosion zone
          let showExplosionMarker = false
          if (inExplosion) {
            const rangeIdx = explosionRanges.findIndex((r) => {
              const t = new Date(item.published_at).getTime()
              return t >= r.start && t <= r.end
            })
            if (rangeIdx !== -1 && rangeIdx !== lastExplosionShown) {
              showExplosionMarker = true
              lastExplosionShown = rangeIdx
            }
          }

          return (
            <div key={item.article_id}>
              {/* Explosion zone marker */}
              {showExplosionMarker && (
                <div className="relative -ml-[21px] mb-3 flex items-center gap-2 sm:-ml-[31px]">
                  <div className="flex h-5 w-5 items-center justify-center rounded-full bg-red-500/20 ring-2 ring-red-500/40">
                    <Zap className="h-3 w-3 text-red-400" />
                  </div>
                  <span className="rounded-md bg-red-500/10 px-2 py-0.5 text-xs font-medium text-red-400">
                    폭발 구간
                  </span>
                </div>
              )}

              {/* Timeline item */}
              <div
                className={`group relative mb-4 ${
                  inExplosion ? 'rounded-lg bg-red-500/[0.04] px-2 py-2 -mx-2 sm:px-3 sm:-mx-3' : ''
                }`}
              >
                {/* Dot on the timeline line */}
                <div
                  className="absolute -left-[21px] top-2 h-3 w-3 rounded-full border-2 sm:-left-[31px]"
                  style={{
                    borderColor: color,
                    backgroundColor: item.is_origin ? color : 'transparent',
                  }}
                />

                {/* Time label */}
                <div className="mb-1 text-xs text-muted-foreground">
                  {formatDate(item.published_at)}
                </div>

                {/* Card */}
                <div
                  className={`rounded-lg border border-border/60 bg-card/50 p-3 transition-colors hover:bg-card ${item.is_user_selected && !item.is_origin ? 'ring-1 ring-blue-500/40' : ''}`}
                  style={{ borderLeftColor: item.is_user_selected && !item.is_origin ? '#3b82f6' : color, borderLeftWidth: 3 }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 space-y-1">
                      <h4 className="text-sm font-medium leading-tight">{item.title}</h4>
                      <div className="flex flex-wrap items-center gap-2">
                        {item.publisher && (
                          <span className="text-xs text-muted-foreground">{item.publisher}</span>
                        )}
                        <Badge stage={stage}>{LIFECYCLE_LABELS[stage]}</Badge>
                        {!item.is_origin && (
                          <span className="text-xs tabular-nums text-muted-foreground">
                            유사도 {(item.similarity_score * 100).toFixed(1)}%
                          </span>
                        )}
                        {item.is_origin && (
                          <Badge stage="origin">기원</Badge>
                        )}
                        {item.is_user_selected && !item.is_origin && (
                          <span className="inline-flex items-center gap-0.5 rounded-full bg-blue-500/15 px-2 py-0.5 text-[11px] font-bold text-blue-500">◎ 대표</span>
                        )}
                      </div>
                      {item.summary && (
                        <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground/70">
                          {item.summary}
                        </p>
                      )}
                    </div>
                    {item.url && (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-0.5 shrink-0 text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )
        })}

        {/* End marker */}
        <div className="relative -ml-[19px] flex items-center gap-2 pt-1 sm:-ml-[29px]">
          <div className="h-2 w-2 rounded-full bg-muted-foreground/40" />
          <span className="text-xs text-muted-foreground">타임라인 끝</span>
        </div>
      </div>
    </div>
  )
}
