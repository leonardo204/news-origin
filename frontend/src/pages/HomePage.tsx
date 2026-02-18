import { useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Newspaper, TrendingUp, Clock, Flame, TrendingDown } from 'lucide-react'
import SearchBar from '@/components/search/SearchBar'
import ArticleConfirm from '@/components/search/ArticleConfirm'
import TrackingProgress from '@/components/search/TrackingProgress'
import { Card, CardContent } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import EmptyState from '@/components/ui/EmptyState'
import { useTrackingStore } from '@/stores/useTrackingStore'
import { useTrendStore } from '@/stores/useTrendStore'
import { usePageTitle } from '@/hooks/usePageTitle'
import { formatRelativeTime, truncate } from '@/lib/utils'
import { CATEGORY_LABELS, CATEGORY_COLORS } from '@/lib/constants'
import type { TopicCluster } from '@/types'

export default function HomePage() {
  usePageTitle()
  const navigate = useNavigate()
  const { trackingId, trackingStatus, isPolling, isSearching, searchResult } = useTrackingStore()
  const { articleTrends, isLoading, loadArticleTrends } = useTrendStore()

  // Whether the user is in any step of the search/tracking flow
  const isInSearchFlow = isSearching || !!searchResult || !!trackingStatus

  // 카테고리별 대표 1개 클러스터만 선택
  const trendByCategory = useMemo(() => {
    const clusters = articleTrends?.clusters ?? []
    const seen = new Set<string>()
    return clusters.filter((c) => {
      const cat = c.categories[0]
      if (!cat || seen.has(cat)) return false
      seen.add(cat)
      return true
    })
  }, [articleTrends])

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
          <h1 className={`font-bold tracking-tight transition-all duration-500 ${isInSearchFlow ? 'text-xl sm:text-2xl' : 'text-3xl sm:text-4xl'}`}>
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

        {isLoading && trendByCategory.length === 0 ? (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="p-3 sm:p-4">
                  <Skeleton className="mb-2 h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : !isLoading && trendByCategory.length === 0 ? (
          <EmptyState
            icon={<TrendingDown className="h-10 w-10" />}
            title="실시간 트렌드를 불러오지 못했습니다"
            description="네트워크 연결을 확인하거나 잠시 후 다시 시도해주세요."
            action={{
              label: '다시 시도',
              onClick: () => loadArticleTrends(),
            }}
          />
        ) : trendByCategory.length > 0 ? (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {trendByCategory.map((cluster: TopicCluster) => {
              const primaryCat = cluster.categories[0]
              const isHot = cluster.growth_rate >= 2 || cluster.article_count >= 5
              const catColor = CATEGORY_COLORS[primaryCat] || '#888'
              const publisher = cluster.representative_article?.publisher
              return (
                <Card
                  key={cluster.cluster_id}
                  className="cursor-pointer overflow-hidden transition-all hover:border-lifecycle-origin/50 active:scale-[0.98]"
                  onClick={() => {
                    useTrendStore.getState().toggleCluster(cluster.cluster_id)
                    navigate('/trends')
                  }}
                >
                  <CardContent className="flex p-0">
                    <div className="w-1 shrink-0 rounded-l" style={{ backgroundColor: catColor }} />
                    <div className="flex-1 p-3 sm:p-4">
                      <div className="mb-1 flex items-center gap-1.5">
                        {primaryCat && (
                          <span className="text-[11px] font-medium text-muted-foreground">
                            {CATEGORY_LABELS[primaryCat] || primaryCat}
                          </span>
                        )}
                        {isHot && <Flame className="h-3.5 w-3.5 text-lifecycle-explosion" />}
                      </div>
                      <h3 className="text-[15px] font-medium leading-snug">
                        {truncate(cluster.title, 60)}
                      </h3>
                      <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                        {publisher && (
                          <span className="truncate font-medium">{publisher}</span>
                        )}
                        <span className="flex items-center gap-1">
                          <Newspaper className="h-3 w-3" />
                          {cluster.article_count}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatRelativeTime(cluster.last_seen)}
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        ) : (
          <EmptyState
            icon={<TrendingUp className="h-10 w-10" />}
            title="아직 트렌드가 없습니다"
            description="기사가 수집되면 트렌드가 표시됩니다. 30분마다 자동으로 수집합니다."
          />
        )}
      </div>
    </div>
  )
}
