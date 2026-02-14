import { useEffect, useMemo } from 'react'
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
import { CATEGORY_KEYS, CATEGORY_LABELS, CATEGORY_BG } from '@/lib/constants'
import type { TopicCluster } from '@/types'

export default function HomePage() {
  usePageTitle()
  const navigate = useNavigate()
  const { trackingId, trackingStatus, isPolling, isSearching, searchResult } = useTrackingStore()
  const { articleTrends, isLoading, loadArticleTrends } = useTrendStore()

  // Whether the user is in any step of the search/tracking flow
  const isInSearchFlow = isSearching || !!searchResult || !!trackingStatus

  const clusters = articleTrends?.clusters ?? []

  // Group clusters by primary category (first category)
  const categoryGroups = useMemo(() => {
    const groups: Record<string, TopicCluster[]> = {}
    for (const cat of CATEGORY_KEYS) {
      groups[cat] = []
    }
    for (const cluster of clusters) {
      const primaryCat = cluster.categories[0]
      if (primaryCat && groups[primaryCat]) {
        if (groups[primaryCat].length < 2) {
          groups[primaryCat].push(cluster)
        }
      }
    }
    // Filter out empty categories
    return CATEGORY_KEYS
      .filter((cat) => groups[cat].length > 0)
      .map((cat) => ({ category: cat, clusters: groups[cat] }))
  }, [clusters])

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
          {/* Section Header */}
          <div className="mb-4">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <TrendingUp className="h-5 w-5 text-lifecycle-explosion" />
              실시간 트렌드
            </h2>
          </div>

          {isLoading && clusters.length === 0 ? (
            <div>
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
          ) : categoryGroups.length > 0 ? (
            <div className="space-y-5">
              {categoryGroups.map(({ category, clusters: catClusters }) => (
                <div key={category}>
                  <div className="mb-2 flex items-center gap-2">
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-medium ${CATEGORY_BG[category] || 'bg-muted text-muted-foreground'}`}
                    >
                      {CATEGORY_LABELS[category] || category}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {catClusters.map((cluster: TopicCluster) => (
                      <Card
                        key={cluster.cluster_id}
                        className="cursor-pointer transition-colors hover:border-lifecycle-origin/50"
                        onClick={() => navigate('/trends')}
                      >
                        <CardContent className="p-4">
                          <h3 className="mb-2 text-sm font-medium leading-tight">
                            {truncate(cluster.title, 60)}
                          </h3>
                          <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <span className="flex items-center gap-1">
                              <Flame className="h-3 w-3" />
                              {cluster.article_count}건
                            </span>
                            <span className="flex items-center gap-1">
                              <Users className="h-3 w-3" />
                              {cluster.publishers.length}개 언론사
                            </span>
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {formatRelativeTime(cluster.last_seen)}
                            </span>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>

      </div>
    </div>
  )
}
