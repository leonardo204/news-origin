import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Newspaper, TrendingUp, BarChart3, Clock, Database, Zap } from 'lucide-react'
import SearchBar from '@/components/search/SearchBar'
import ArticleConfirm from '@/components/search/ArticleConfirm'
import TrackingProgress from '@/components/search/TrackingProgress'
import { Card, CardContent } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { useTrackingStore } from '@/stores/useTrackingStore'
import { useTrendStore } from '@/stores/useTrendStore'
import { usePageTitle } from '@/hooks/usePageTitle'
import { formatRelativeTime, truncate } from '@/lib/utils'

const CATEGORY_LABELS: Record<string, string> = {
  headlines: '헤드라인',
  politics: '정치',
  economy: '경제',
  society: '사회',
  tech: 'IT/과학',
  entertainment: '연예/문화',
}

export default function HomePage() {
  usePageTitle()
  const navigate = useNavigate()
  const { trackingId, trackingStatus, isPolling, isSearching, searchResult } = useTrackingStore()
  const { trends, stats, isLoading, loadTrends, loadStats } = useTrendStore()

  // Whether the user is in any step of the search/tracking flow
  const isInSearchFlow = isSearching || !!searchResult || !!trackingStatus

  useEffect(() => {
    loadTrends()
    loadStats()

    // SSE: 크롤링 완료 시 실시간 갱신
    const es = new EventSource('/api/trends/events')
    es.onmessage = () => {
      loadStats()
      loadTrends()
    }
    es.onerror = () => {
      // SSE 연결 실패 시 조용히 무시 (브라우저가 자동 재연결)
    }

    // Clear stale completed tracking state so we don't auto-redirect
    // back to the timeline page the user just left
    const state = useTrackingStore.getState()
    if (state.trackingStatus?.status === 'completed' && !state.isPolling) {
      useTrackingStore.setState({ trackingId: null, trackingStatus: null, timeline: null })
    }

    return () => es.close()
  }, [loadTrends, loadStats])

  // Navigate to timeline when tracking is complete
  useEffect(() => {
    if (trackingId && trackingStatus?.status === 'completed' && !isPolling) {
      navigate(`/timeline/${trackingId}`)
    }
  }, [trackingId, trackingStatus, isPolling, navigate])

  return (
    <div className="relative mx-auto max-w-7xl px-4 py-8">
      {/* Sidebar: Stats + Category — pinned to top-right on desktop */}
      <div className={`transition-all duration-500 ${isInSearchFlow ? 'pointer-events-none lg:opacity-0' : 'lg:opacity-100'} mt-8 space-y-3 lg:absolute lg:right-0 lg:top-12 lg:z-10 lg:mt-0 lg:w-52`}>
        {stats ? (
          <>
            <Card>
              <CardContent className="px-4 py-3">
                <div className="space-y-2.5">
                  <StatRow icon={<BarChart3 className="h-3.5 w-3.5 text-lifecycle-spread" />} label="총 추적" value={stats.total_trackings} />
                  <StatRow icon={<Newspaper className="h-3.5 w-3.5 text-lifecycle-origin" />} label="수집된 기사" value={stats.total_articles} />
                  <StatRow icon={<TrendingUp className="h-3.5 w-3.5 text-lifecycle-explosion" />} label="진행 중" value={stats.active_trackings} />
                  <div className="border-t border-border" />
                  <StatRow icon={<Database className="h-3.5 w-3.5 text-lifecycle-sustained" />} label="임베딩 완료" value={stats.embedded_articles} />
                  <StatRow icon={<Zap className="h-3.5 w-3.5 text-lifecycle-resurge" />} label="최근 24h 수집" value={stats.recent_articles_24h} />
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="text-[13px] text-muted-foreground">마지막 크롤링</span>
                    </div>
                    <span className="text-[13px] font-medium tabular-nums">
                      {stats.last_crawl_at ? formatRelativeTime(stats.last_crawl_at) : '-'}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
            {Object.keys(stats.category_counts).length > 0 && (
              <CategoryDistribution counts={stats.category_counts} />
            )}
          </>
        ) : isLoading ? (
          <Card>
            <CardContent className="space-y-3 px-4 py-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Skeleton className="h-3.5 w-3.5 rounded" />
                    <Skeleton className="h-3 w-16" />
                  </div>
                  <Skeleton className="h-3 w-10" />
                </div>
              ))}
            </CardContent>
          </Card>
        ) : null}
      </div>

      {/* Hero section */}
      <div className={`flex flex-col items-center gap-6 transition-all duration-500 ${isInSearchFlow ? 'py-6' : 'py-12'}`}>
        <div className="flex items-center gap-3">
          <Newspaper className={`text-lifecycle-origin transition-all duration-500 ${isInSearchFlow ? 'h-7 w-7' : 'h-10 w-10'}`} />
          <h1 className={`font-bold tracking-tight transition-all duration-500 ${isInSearchFlow ? 'text-2xl' : 'text-4xl'}`}>
            News <span className="text-lifecycle-origin">Origin</span>
          </h1>
        </div>
        <p className={`max-w-lg text-center text-muted-foreground transition-all duration-500 ${isInSearchFlow ? 'h-0 overflow-hidden opacity-0' : 'opacity-100'}`}>
          뉴스 기사의 기원을 추적하고, 확산 경로를 시각화합니다.
          <br />
          URL 또는 기사 제목을 입력하여 시작하세요.
        </p>

        <SearchBar />
        <ArticleConfirm />
        <TrackingProgress />
      </div>

      {/* Trends — hidden during search flow */}
      <div className={`transition-all duration-500 ${isInSearchFlow ? 'pointer-events-none h-0 overflow-hidden opacity-0' : 'opacity-100'}`}>
        <div className="mx-auto max-w-2xl">
          {isLoading && trends.length === 0 ? (
            <div>
              <Skeleton className="mb-4 h-6 w-36" />
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Card key={i}>
                    <CardContent className="p-4">
                      <Skeleton className="mb-2 h-4 w-3/4" />
                      <div className="flex items-center justify-between">
                        <Skeleton className="h-3 w-16" />
                        <Skeleton className="h-3 w-12" />
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          ) : trends.length > 0 ? (
            <div>
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
                <TrendingUp className="h-5 w-5 text-lifecycle-explosion" />
                실시간 트렌드
              </h2>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {trends.slice(0, 6).map((trend) => (
                  <Card
                    key={trend.latest_tracking_id}
                    className="cursor-pointer transition-colors hover:border-lifecycle-origin/50"
                    onClick={() => navigate(`/timeline/${trend.latest_tracking_id}`)}
                  >
                    <CardContent className="p-4">
                      <h3 className="mb-2 text-sm font-medium leading-tight">
                        {truncate(trend.title, 60)}
                      </h3>
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <BarChart3 className="h-3 w-3" />
                          {trend.tracking_count}회 추적
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatRelativeTime(trend.last_tracked_at)}
                        </span>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          ) : null}
        </div>

      </div>
    </div>
  )
}

function StatRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: number
}) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-[13px] text-muted-foreground">{label}</span>
      </div>
      <span className="text-[13px] font-medium tabular-nums">{value.toLocaleString()}</span>
    </div>
  )
}

const CATEGORY_COLORS: Record<string, string> = {
  headlines: 'bg-emerald-400',
  politics: 'bg-blue-400',
  economy: 'bg-amber-400',
  society: 'bg-rose-400',
  tech: 'bg-violet-400',
  entertainment: 'bg-cyan-400',
}

function CategoryDistribution({
  counts,
}: {
  counts: Record<string, number>
}) {
  const sorted = Object.entries(counts).sort(([, a], [, b]) => b - a)
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0)
  const maxCount = Math.max(...Object.values(counts))

  return (
    <Card>
      <CardContent className="px-5 py-4">
        <div className="mb-4 flex items-baseline justify-between">
          <h3 className="text-[13px] font-medium text-muted-foreground">
            카테고리별 수집 현황
          </h3>
          <span className="text-[11px] tabular-nums text-muted-foreground/60">
            총 {total.toLocaleString()}건
          </span>
        </div>
        <div className="space-y-3">
          {sorted.map(([category, count]) => {
            const pct = total > 0 ? Math.round((count / total) * 100) : 0
            return (
              <div key={category} className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className={`h-2 w-2 shrink-0 rounded-full ${CATEGORY_COLORS[category] || 'bg-muted-foreground'}`}
                    />
                    <span className="text-[13px] text-foreground/80">
                      {CATEGORY_LABELS[category] || category}
                    </span>
                  </div>
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-[13px] font-medium tabular-nums">
                      {count.toLocaleString()}
                    </span>
                    <span className="w-8 text-right text-[11px] tabular-nums text-muted-foreground/50">
                      {pct}%
                    </span>
                  </div>
                </div>
                <div className="h-1.5 overflow-hidden rounded-sm bg-muted/40">
                  <div
                    className={`h-full rounded-sm ${CATEGORY_COLORS[category] || 'bg-primary'}`}
                    style={{ width: `${(count / maxCount) * 100}%`, opacity: 0.65 }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
