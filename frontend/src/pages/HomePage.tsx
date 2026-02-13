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
  const { trackingId, trackingStatus, isPolling, isSearching, searchResult } = useTrackingStore()
  const { trends, isLoading, loadTrends } = useTrendStore()

  // Whether the user is in any step of the search/tracking flow
  const isInSearchFlow = isSearching || !!searchResult || !!trackingStatus

  useEffect(() => {
    loadTrends()

    // SSE: 크롤링 완료 시 실시간 갱신
    const es = new EventSource('/api/trends/events')
    es.onmessage = () => {
      loadTrends()
    }
    es.onerror = () => {
      // SSE 연결 실패 시 조용히 무시 (브라우저가 자동 재연결)
    }

    return () => es.close()
  }, [loadTrends])

  // Navigate to timeline when tracking is complete
  useEffect(() => {
    if (trackingId && trackingStatus?.status === 'completed' && !isPolling) {
      navigate(`/timeline/${trackingId}`)
    }
  }, [trackingId, trackingStatus, isPolling, navigate])

  return (
    <div className="relative mx-auto max-w-7xl px-4 py-8">
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

