import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Newspaper, TrendingUp, BarChart3, Clock } from 'lucide-react'
import SearchBar from '@/components/search/SearchBar'
import ArticleConfirm from '@/components/search/ArticleConfirm'
import TrackingProgress from '@/components/search/TrackingProgress'
import { Card, CardContent } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { useTrackingStore } from '@/stores/useTrackingStore'
import { useTrendStore } from '@/stores/useTrendStore'
import { usePageTitle } from '@/hooks/usePageTitle'
import { formatRelativeTime, truncate } from '@/lib/utils'

export default function HomePage() {
  usePageTitle()
  const navigate = useNavigate()
  const { trackingId, trackingStatus, isPolling } = useTrackingStore()
  const { trends, stats, isLoading, loadTrends, loadStats } = useTrendStore()

  useEffect(() => {
    loadTrends()
    loadStats()
  }, [loadTrends, loadStats])

  // Navigate to timeline when tracking is complete
  useEffect(() => {
    if (trackingId && trackingStatus?.status === 'completed' && !isPolling) {
      navigate(`/timeline/${trackingId}`)
    }
  }, [trackingId, trackingStatus, isPolling, navigate])

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {/* Hero section */}
      <div className="flex flex-col items-center gap-6 py-12">
        <div className="flex items-center gap-3">
          <Newspaper className="h-10 w-10 text-lifecycle-origin" />
          <h1 className="text-4xl font-bold tracking-tight">
            News <span className="text-lifecycle-origin">Origin</span>
          </h1>
        </div>
        <p className="max-w-lg text-center text-muted-foreground">
          뉴스 기사의 기원을 추적하고, 확산 경로를 시각화합니다.
          <br />
          URL 또는 기사 제목을 입력하여 시작하세요.
        </p>

        <SearchBar />
        <ArticleConfirm />
        <TrackingProgress />
      </div>

      {/* Stats */}
      {stats ? (
        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            icon={<BarChart3 className="h-5 w-5 text-lifecycle-spread" />}
            label="총 추적"
            value={stats.total_trackings}
          />
          <StatCard
            icon={<Newspaper className="h-5 w-5 text-lifecycle-origin" />}
            label="수집된 기사"
            value={stats.total_articles}
          />
          <StatCard
            icon={<TrendingUp className="h-5 w-5 text-lifecycle-explosion" />}
            label="진행 중"
            value={stats.active_trackings}
          />
        </div>
      ) : isLoading ? (
        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="flex items-center gap-3 p-4">
                <Skeleton className="h-5 w-5 rounded" />
                <div className="space-y-1">
                  <Skeleton className="h-3 w-12" />
                  <Skeleton className="h-7 w-16" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      {/* Hot trends */}
      {isLoading && trends.length === 0 ? (
        <div>
          <Skeleton className="mb-4 h-6 w-36" />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
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
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
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
  )
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: number
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        {icon}
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold tabular-nums">{value.toLocaleString()}</p>
        </div>
      </CardContent>
    </Card>
  )
}
