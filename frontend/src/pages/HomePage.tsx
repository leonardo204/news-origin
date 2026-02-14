import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Newspaper, TrendingUp, Clock, Flame, Users } from 'lucide-react'
import SearchBar from '@/components/search/SearchBar'
import ArticleConfirm from '@/components/search/ArticleConfirm'
import TrackingProgress from '@/components/search/TrackingProgress'
import { Card, CardContent } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { useTrackingStore } from '@/stores/useTrackingStore'
import { useTrendStore } from '@/stores/useTrendStore'
import { usePageTitle } from '@/hooks/usePageTitle'
import { formatRelativeTime, truncate } from '@/lib/utils'
import { CATEGORY_LABELS, CATEGORY_BG } from '@/lib/constants'
import type { TopicCluster } from '@/types'

export default function HomePage() {
  usePageTitle()
  const navigate = useNavigate()
  const { trackingId, trackingStatus, isPolling, isSearching, searchResult } = useTrackingStore()
  const { articleTrends, isLoading, loadArticleTrends } = useTrendStore()

  // Whether the user is in any step of the search/tracking flow
  const isInSearchFlow = isSearching || !!searchResult || !!trackingStatus

  const clusters = articleTrends?.clusters ?? []

  useEffect(() => {
    loadArticleTrends()
  }, [loadArticleTrends])

  // Navigate to timeline when tracking is complete
  useEffect(() => {
    if (trackingId && trackingStatus?.status === 'completed' && !isPolling) {
      navigate(`/timeline/${trackingId}`)
    }
  }, [trackingId, trackingStatus, isPolling, navigate])

  return (
    <div className="relative mx-auto max-w-7xl px-4 py-8">
      {/* Hero section */}
      <div className={`flex flex-col items-center gap-6 transition-all duration-500 ${isInSearchFlow ? 'py-6' : 'py-8'}`}>
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
      <div className={`transition-all duration-500 ${isInSearchFlow ? 'pointer-events-none h-0 overflow-hidden opacity-0' : 'mt-2 opacity-100'}`}>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <TrendingUp className="h-5 w-5 text-lifecycle-explosion" />
            실시간 트렌드
          </h2>
          <button
            onClick={() => navigate('/trends')}
            className="text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            전체 보기 &rarr;
          </button>
        </div>

        {isLoading && clusters.length === 0 ? (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="p-3">
                  <Skeleton className="mb-1.5 h-3.5 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : clusters.length > 0 ? (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            {clusters.slice(0, 12).map((cluster: TopicCluster, i: number) => {
              const primaryCat = cluster.categories[0]
              const isHot = cluster.growth_rate >= 2 || cluster.article_count >= 5
              return (
                <Card
                  key={cluster.cluster_id}
                  className="cursor-pointer transition-colors hover:border-lifecycle-origin/50"
                  onClick={() => navigate('/trends')}
                >
                  <CardContent className="p-3">
                    <div className="mb-1.5 flex items-center gap-1.5">
                      <span className="text-[11px] font-bold text-muted-foreground/60">
                        {i + 1}
                      </span>
                      {primaryCat && (
                        <span
                          className={`rounded px-1 py-0.5 text-[9px] font-medium leading-none ${CATEGORY_BG[primaryCat] || 'bg-muted text-muted-foreground'}`}
                        >
                          {CATEGORY_LABELS[primaryCat] || primaryCat}
                        </span>
                      )}
                      {isHot && <Flame className="h-3 w-3 text-lifecycle-explosion" />}
                    </div>
                    <h3 className="text-[13px] font-medium leading-tight">
                      {truncate(cluster.title, 45)}
                    </h3>
                    <div className="mt-1.5 flex items-center gap-2 text-[11px] text-muted-foreground">
                      <span className="flex items-center gap-0.5">
                        <Newspaper className="h-2.5 w-2.5" />
                        {cluster.article_count}
                      </span>
                      <span className="flex items-center gap-0.5">
                        <Users className="h-2.5 w-2.5" />
                        {cluster.publishers.length}
                      </span>
                      <span className="flex items-center gap-0.5">
                        <Clock className="h-2.5 w-2.5" />
                        {formatRelativeTime(cluster.last_seen)}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        ) : null}
      </div>
    </div>
  )
}
