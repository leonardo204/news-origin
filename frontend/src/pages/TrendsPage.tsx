import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  TrendingUp,
  Newspaper,
  Flame,
  Clock,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Users,
  Layers,
  LayoutGrid,
  List,
  X,
  Filter,
  ArrowUpRight,
  ArrowDownRight,
  ArrowLeftRight,
  Sparkles,
} from 'lucide-react'
import ReactECharts from 'echarts-for-react'
import echarts from '@/lib/echarts'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import EmptyState from '@/components/ui/EmptyState'
import ArticleCompare from '@/components/ArticleCompare'
import { useTrendStore } from '@/stores/useTrendStore'
import { useTrackingStore } from '@/stores/useTrackingStore'
import { usePageTitle } from '@/hooks/usePageTitle'
import { formatRelativeTime, truncate } from '@/lib/utils'
import { CATEGORY_KEYS, CATEGORY_LABELS, CATEGORY_COLORS, CATEGORY_BG } from '@/lib/constants'
import { compareTrends } from '@/services/api'
import type { TopicCluster, ClusterArticle, TrendComparison } from '@/types'

interface EChartsTooltipParam {
  name?: string
  value?: number | number[]
  seriesName?: string
  data?: { value?: number; name?: string }
  marker?: string
  percent?: number
}

interface EChartsClickParam {
  name?: string
  value?: number
  data?: Record<string, unknown>
}

export default function TrendsPage() {
  usePageTitle('트렌드')
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const {
    articleTrends,
    recentArticles,
    expandedClusterId,
    isLoading,
    error,
    period,
    trendView,
    setPeriod,
    setTrendView,
    toggleCluster,
    loadArticleTrends,
    loadRecentArticles,
  } = useTrendStore()

  // Read filters from URL
  const selectedCategories = useMemo(() => {
    const cats = searchParams.get('categories')
    return cats ? cats.split(',').filter(Boolean) : []
  }, [searchParams])

  const selectedPublisher = searchParams.get('publisher') || null

  useEffect(() => {
    loadArticleTrends()
    loadRecentArticles()
  }, [loadArticleTrends, loadRecentArticles])

  // Group clusters by primary category for category view
  const categoryGroups = useMemo(() => {
    const clusters = articleTrends?.clusters ?? []
    const groups: Record<string, TopicCluster[]> = {}
    for (const cat of CATEGORY_KEYS) {
      groups[cat] = []
    }
    for (const cluster of clusters) {
      const primaryCat = cluster.categories[0]
      if (primaryCat && groups[primaryCat]) {
        groups[primaryCat].push(cluster)
      }
    }
    return CATEGORY_KEYS.map((cat) => ({ category: cat, clusters: groups[cat] }))
  }, [articleTrends])

  // Top 10 publishers from publisher_distribution
  const topPublishers = useMemo(() => {
    if (!articleTrends?.publisher_distribution) return []
    return Object.entries(articleTrends.publisher_distribution)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 10)
      .map(([pub]) => pub)
  }, [articleTrends])

  const filteredClusters = useMemo(() => {
    let clusters = articleTrends?.clusters ?? []

    // Filter by categories
    if (selectedCategories.length > 0) {
      clusters = clusters.filter((c) =>
        c.categories.some((cat) => selectedCategories.includes(cat))
      )
    }

    // Filter by publisher
    if (selectedPublisher) {
      clusters = clusters.filter((c) => c.publishers.includes(selectedPublisher))
    }

    return clusters
  }, [articleTrends, selectedCategories, selectedPublisher])

  const toggleCategory = useCallback((cat: string) => {
    const newCategories = selectedCategories.includes(cat)
      ? selectedCategories.filter((c) => c !== cat)
      : [...selectedCategories, cat]

    const params = new URLSearchParams(searchParams)
    if (newCategories.length > 0) {
      params.set('categories', newCategories.join(','))
    } else {
      params.delete('categories')
    }
    setSearchParams(params)
  }, [selectedCategories, searchParams, setSearchParams])

  const setPublisher = useCallback((pub: string | null) => {
    const params = new URLSearchParams(searchParams)
    if (pub) {
      params.set('publisher', pub)
    } else {
      params.delete('publisher')
    }
    setSearchParams(params)
  }, [searchParams, setSearchParams])

  const clearFilters = useCallback(() => {
    setSearchParams(new URLSearchParams())
  }, [setSearchParams])

  const hasActiveFilters = selectedCategories.length > 0 || selectedPublisher !== null

  const [categoryFilterExpanded, setCategoryFilterExpanded] = useState(false)

  // Comparison state
  const [comparison, setComparison] = useState<TrendComparison | null>(null)
  const [isLoadingComparison, setIsLoadingComparison] = useState(false)
  const [comparisonError, setComparisonError] = useState<string | null>(null)

  // Article compare modal state
  const [compareCluster, setCompareCluster] = useState<TopicCluster | null>(null)

  // Scroll to expanded cluster (e.g. when coming from HomePage)
  useEffect(() => {
    if (!expandedClusterId) return
    const timer = setTimeout(() => {
      const el = document.querySelector(`[data-cluster-id="${expandedClusterId}"]`)
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 100)
    return () => clearTimeout(timer)
  // Only on mount or when navigating with a pre-set cluster
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Collapse expanded cluster on outside click
  useEffect(() => {
    if (!expandedClusterId) return
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (!target.closest('[data-cluster-card]')) {
        toggleCluster(expandedClusterId)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [expandedClusterId, toggleCluster])

  // View toggle / period change clears all filters + expanded state
  const handleSetTrendView = useCallback((view: 'overall' | 'category' | 'compare') => {
    setTrendView(view)
    if (view === 'compare') {
      loadComparison()
    }
  }, [setTrendView])

  // Sync period from URL on mount
  const urlPeriod = searchParams.get('period') as '24h' | '7d' | '30d' | null
  useEffect(() => {
    if (urlPeriod && ['24h', '7d', '30d'].includes(urlPeriod) && urlPeriod !== period) {
      setPeriod(urlPeriod)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSetPeriod = useCallback((p: '24h' | '7d' | '30d') => {
    setPeriod(p)
    const params = new URLSearchParams(searchParams)
    if (p !== '24h') {
      params.set('period', p)
    } else {
      params.delete('period')
    }
    setSearchParams(params)
    if (trendView === 'compare') {
      loadComparison()
    }
  }, [setPeriod, trendView, searchParams, setSearchParams])

  const loadComparison = useCallback(async () => {
    setIsLoadingComparison(true)
    setComparisonError(null)
    try {
      const periodB = period === '24h' ? '7d' : period === '7d' ? '30d' : '7d'
      const data = await compareTrends(period, periodB)
      setComparison(data)
    } catch (err) {
      setComparisonError(err instanceof Error ? err.message : '비교 데이터를 불러올 수 없습니다')
    } finally {
      setIsLoadingComparison(false)
    }
  }, [period])

  const handleTrack = (article: ClusterArticle) => {
    useTrackingStore.getState().reset()
    // Navigate immediately for instant feedback, then start tracking in background
    navigate('/')
    useTrackingStore.getState().selectCandidate({
      url: article.url,
      title: article.title,
      publisher: article.publisher ?? undefined,
      published_at: article.published_at ?? undefined,
    })
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {/* Header */}
      <div className="mb-8 flex flex-wrap items-center justify-between gap-3">
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <TrendingUp className="h-6 w-6 text-lifecycle-explosion" />
          뉴스 트렌드
        </h1>
        {/* Period Filter */}
        <div className="inline-flex items-center rounded-lg border border-border bg-secondary/50 p-1">
          {(['24h', '7d', '30d'] as const).map((p) => (
            <button
              key={p}
              onClick={() => handleSetPeriod(p)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                period === p
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {p === '24h' ? '24시간' : p === '7d' ? '7일' : '30일'}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Filters */}
      {!isLoading && articleTrends && (
        <div className="mb-6 space-y-3">
          {/* Category Filter */}
          <div className="rounded-lg border border-border bg-secondary/20 p-3">
            <button
              onClick={() => setCategoryFilterExpanded(!categoryFilterExpanded)}
              className="flex w-full items-center justify-between md:hidden"
              aria-label="카테고리 필터 토글"
              aria-expanded={categoryFilterExpanded}
            >
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Filter className="h-4 w-4" />
                <span className="font-medium">카테고리</span>
                {selectedCategories.length > 0 && (
                  <span className="rounded-full bg-lifecycle-origin/20 px-2 py-0.5 text-xs font-medium text-lifecycle-origin">
                    {selectedCategories.length}
                  </span>
                )}
              </div>
              {categoryFilterExpanded ? (
                <ChevronUp className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              )}
            </button>
            <div className={`${categoryFilterExpanded ? 'mt-3' : 'hidden'} md:block`}>
              <div className="hidden items-center gap-2 text-sm text-muted-foreground md:flex md:mb-2">
                <Filter className="h-4 w-4" />
                <span className="font-medium">카테고리:</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {CATEGORY_KEYS.map((cat) => {
                  const isSelected = selectedCategories.includes(cat)
                  return (
                    <button
                      key={cat}
                      onClick={() => toggleCategory(cat)}
                      className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium transition-all ${
                        isSelected
                          ? CATEGORY_BG[cat] || 'bg-primary/20 text-primary'
                          : 'border border-border bg-secondary/30 text-muted-foreground hover:bg-secondary'
                      }`}
                      aria-label={`${CATEGORY_LABELS[cat]} 카테고리 필터 ${isSelected ? '해제' : '적용'}`}
                    >
                      {CATEGORY_LABELS[cat] || cat}
                    </button>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Publisher Filter */}
          {topPublishers.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Users className="h-4 w-4" />
                <span className="font-medium">언론사:</span>
              </div>
              <select
                value={selectedPublisher || ''}
                onChange={(e) => setPublisher(e.target.value || null)}
                className="rounded-lg border border-border bg-secondary/50 px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-secondary focus:outline-none focus:ring-2 focus:ring-lifecycle-origin/50"
              >
                <option value="">전체</option>
                {topPublishers.map((pub) => (
                  <option key={pub} value={pub}>
                    {pub}
                  </option>
                ))}
              </select>
              {hasActiveFilters && (
                <button
                  onClick={clearFilters}
                  className="flex items-center gap-1 rounded-lg border border-border bg-secondary/50 px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                >
                  <X className="h-3 w-3" />
                  필터 초기화
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {isLoading ? (
        <LoadingSkeleton />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_340px]">
          {/* Left: Main Content */}
          <div className="space-y-6">
            {/* Topic Clusters */}
            <Card>
              <CardHeader>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <Flame className="h-4 w-4 text-lifecycle-explosion" />
                    트렌딩 토픽
                  </CardTitle>
                  {/* View Toggle */}
                  <div className="inline-flex items-center rounded-lg border border-border bg-secondary/50 p-1">
                    <button
                      onClick={() => handleSetTrendView('overall')}
                      className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors sm:px-3 ${
                        trendView === 'overall'
                          ? 'bg-background text-foreground shadow-sm'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      <List className="h-3.5 w-3.5" />
                      종합 순위
                    </button>
                    <button
                      onClick={() => handleSetTrendView('category')}
                      className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors sm:px-3 ${
                        trendView === 'category'
                          ? 'bg-background text-foreground shadow-sm'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      <LayoutGrid className="h-3.5 w-3.5" />
                      카테고리별
                    </button>
                    <button
                      onClick={() => handleSetTrendView('compare')}
                      className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors sm:px-3 ${
                        trendView === 'compare'
                          ? 'bg-background text-foreground shadow-sm'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      <Sparkles className="h-3.5 w-3.5" />
                      비교
                    </button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {!articleTrends || filteredClusters.length === 0 ? (
                  <EmptyState
                    icon={<Newspaper className="h-10 w-10" />}
                    title={hasActiveFilters ? '필터 조건에 맞는 트렌드가 없습니다' : '현재 분석 중인 트렌드가 없습니다'}
                    description={
                      hasActiveFilters
                        ? '다른 필터 조건을 선택하거나 초기화해보세요.'
                        : '더 많은 기사가 수집되면 트렌드가 나타납니다. 30분마다 자동으로 기사를 수집합니다.'
                    }
                    action={
                      hasActiveFilters
                        ? {
                            label: '필터 초기화',
                            onClick: clearFilters,
                          }
                        : undefined
                    }
                  />
                ) : trendView === 'compare' ? (
                  /* Comparison View */
                  <ComparisonView
                    comparison={comparison}
                    isLoading={isLoadingComparison}
                    error={comparisonError}
                  />
                ) : trendView === 'overall' ? (
                  /* Overall Ranking */
                  <div className="space-y-2">
                    {filteredClusters.map((cluster, i) => (
                      <TopicClusterCard
                        key={cluster.cluster_id}
                        cluster={cluster}
                        rank={i + 1}
                        isExpanded={expandedClusterId === cluster.cluster_id}
                        onToggle={() => toggleCluster(cluster.cluster_id)}
                        onTrack={handleTrack}
                        onCompare={setCompareCluster}
                      />
                    ))}
                  </div>
                ) : (
                  /* Category View */
                  <div className="space-y-6">
                    {categoryGroups
                      .filter(({ clusters: catClusters }) => catClusters.length > 0)
                      .map(({ category, clusters: catClusters }) => (
                      <div key={category}>
                        <div className="mb-3 flex items-center gap-2">
                          <span
                            className={`rounded px-2 py-1 text-xs font-semibold ${CATEGORY_BG[category] || 'bg-muted text-muted-foreground'}`}
                          >
                            {CATEGORY_LABELS[category] || category}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {catClusters.length}개 토픽
                          </span>
                        </div>
                        <div className="space-y-2">
                          {catClusters.map((cluster, i) => (
                            <TopicClusterCard
                              key={cluster.cluster_id}
                              cluster={cluster}
                              rank={i + 1}
                              isExpanded={expandedClusterId === cluster.cluster_id}
                              onToggle={() => toggleCluster(cluster.cluster_id)}
                              onTrack={handleTrack}
                              onCompare={setCompareCluster}
                            />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

          </div>

          {/* Right: Sidebar */}
          <div className="space-y-6">
            {/* Category Distribution */}
            {articleTrends && Object.keys(articleTrends.category_distribution).length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Layers className="h-4 w-4 text-lifecycle-spread" />
                    카테고리 분포
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ReactECharts
                    echarts={echarts}
                    notMerge
                    option={{
                      backgroundColor: 'transparent',
                      tooltip: {
                        backgroundColor: '#1f2937',
                        borderColor: '#374151',
                        textStyle: { color: '#e5e7eb', fontSize: 12 },
                        formatter: (params: EChartsTooltipParam) =>
                          `${params.name}: ${params.value}건 (${params.percent}%)`,
                      },
                      series: [
                        {
                          type: 'pie',
                          radius: ['45%', '75%'],
                          avoidLabelOverlap: true,
                          itemStyle: { borderRadius: 4, borderColor: '#0a0a0a', borderWidth: 2 },
                          label: {
                            color: '#9ca3af',
                            fontSize: 11,
                            formatter: '{b}\n{d}%',
                          },
                          emphasis: {
                            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' },
                            label: { fontWeight: 'bold' },
                          },
                          data: Object.entries(articleTrends.category_distribution).map(
                            ([cat, count]) => ({
                              name: CATEGORY_LABELS[cat] || cat,
                              value: count,
                              itemStyle: {
                                color: CATEGORY_COLORS[cat] || '#6b7280',
                                opacity: selectedCategories.length > 0 && !selectedCategories.includes(cat) ? 0.3 : 1,
                              },
                            }),
                          ),
                        },
                      ],
                    }}
                    style={{ height: 200, cursor: 'pointer' }}
                    theme="dark"
                    onEvents={{
                      click: (params: EChartsClickParam) => {
                        const catKey = Object.entries(CATEGORY_LABELS).find(
                          ([, label]) => label === params.name,
                        )?.[0]
                        if (catKey) {
                          toggleCategory(catKey)
                          if (trendView !== 'overall') {
                            setTrendView('overall')
                          }
                        }
                      },
                    }}
                  />
                </CardContent>
              </Card>
            )}

            {/* Publisher Ranking */}
            {articleTrends && Object.keys(articleTrends.publisher_distribution).length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-lifecycle-sustained" />
                    언론사 랭킹
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {Object.entries(articleTrends.publisher_distribution)
                      .sort(([, a], [, b]) => b - a)
                      .slice(0, 10)
                      .map(([pub, count]) => {
                        const maxCount = Math.max(
                          ...Object.values(articleTrends.publisher_distribution),
                        )
                        return (
                          <div key={pub} className="space-y-1">
                            <div className="flex items-center justify-between text-[12px]">
                              <span className="truncate text-foreground/80">{pub}</span>
                              <span className="ml-2 shrink-0 font-medium tabular-nums">
                                {count}
                              </span>
                            </div>
                            <div className="h-1 overflow-hidden rounded-sm bg-muted/40">
                              <div
                                className="h-full rounded-sm bg-lifecycle-sustained"
                                style={{ width: `${(count / maxCount) * 100}%`, opacity: 0.6 }}
                              />
                            </div>
                          </div>
                        )
                      })}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Recent Articles Feed */}
            {recentArticles.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    최근 수집
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1">
                    {recentArticles.slice(0, 15).map((a) => (
                      <a
                        key={a.id}
                        href={a.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block rounded-md px-2 py-1.5 transition-colors hover:bg-secondary/30"
                      >
                        <p className="text-[12px] font-medium leading-tight text-foreground/90">
                          {truncate(a.title, 50)}
                        </p>
                        <div className="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground">
                          {a.publisher && <span>{a.publisher}</span>}
                          {a.category && (
                            <span
                              className={`rounded px-1 py-0.5 text-[9px] ${CATEGORY_BG[a.category] || 'bg-muted text-muted-foreground'}`}
                            >
                              {CATEGORY_LABELS[a.category] || a.category}
                            </span>
                          )}
                          <span>{formatRelativeTime(a.created_at)}</span>
                        </div>
                      </a>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

          </div>
        </div>
      )}

      {compareCluster && (
        <ArticleCompare
          articles={compareCluster.articles}
          onClose={() => setCompareCluster(null)}
        />
      )}
    </div>
  )
}

/* ── Topic Cluster Card ── */

function TopicClusterCard({
  cluster,
  rank,
  isExpanded,
  onToggle,
  onTrack,
  onCompare,
}: {
  cluster: TopicCluster
  rank: number
  isExpanded: boolean
  onToggle: () => void
  onTrack: (article: ClusterArticle) => void
  onCompare: (cluster: TopicCluster) => void
}) {
  const isHot = cluster.growth_rate >= 2 || cluster.article_count >= 5

  return (
    <div data-cluster-card data-cluster-id={cluster.cluster_id} className="rounded-lg border border-border/50 transition-colors hover:border-border">
      <button
        onClick={onToggle}
        className="flex w-full items-start gap-3 p-3 sm:p-4 text-left"
      >
        <span
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold ${
            rank <= 3
              ? 'bg-lifecycle-explosion/15 text-lifecycle-explosion'
              : 'bg-secondary text-muted-foreground'
          }`}
        >
          {rank}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <p className="flex-1 text-sm font-medium leading-snug sm:text-[15px]">
              {truncate(cluster.title, 80)}
            </p>
            {isHot && (
              <Flame className="h-4 w-4 shrink-0 text-lifecycle-explosion" />
            )}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 sm:gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1 font-medium text-foreground/80">
              <Newspaper className="h-3 w-3" />
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
          <div className="mt-2 flex flex-wrap gap-1">
            {cluster.categories.map((cat) => (
              <span
                key={cat}
                className={`rounded px-1.5 py-0.5 text-[10px] sm:text-[11px] font-medium ${CATEGORY_BG[cat] || 'bg-muted text-muted-foreground'}`}
              >
                {CATEGORY_LABELS[cat] || cat}
              </span>
            ))}
            {cluster.publishers.length > 0 && (
              <span className="rounded bg-muted/50 px-1.5 py-0.5 text-[10px] sm:text-[11px] text-muted-foreground">
                {cluster.publishers.slice(0, 3).join(', ')}
                {cluster.publishers.length > 3 && ` +${cluster.publishers.length - 3}`}
              </span>
            )}
          </div>
        </div>
        <div className="shrink-0 pt-1">
          {isExpanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="animate-in fade-in slide-in-from-top-1 duration-200 border-t border-border/50 px-3 sm:px-4 pb-3 pt-2">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onTrack(cluster.representative_article)
            }}
            className="mb-2 flex w-full items-center justify-center gap-2 rounded-lg border border-lifecycle-origin/30 bg-lifecycle-origin/10 px-4 py-2.5 text-sm font-medium text-lifecycle-origin transition-colors hover:bg-lifecycle-origin/20 active:scale-[0.98]"
          >
            <Newspaper className="h-4 w-4" />
            이 토픽의 대표 기사 추적 시작
          </button>
          {cluster.articles.length >= 2 && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onCompare(cluster)
              }}
              className="mb-3 flex w-full items-center justify-center gap-2 rounded-lg border border-lifecycle-spread/30 bg-lifecycle-spread/10 px-4 py-2.5 text-sm font-medium text-lifecycle-spread transition-colors hover:bg-lifecycle-spread/20 active:scale-[0.98]"
            >
              <ArrowLeftRight className="h-4 w-4" />
              기사 비교
            </button>
          )}
          <div className="space-y-0.5">
            {cluster.articles.map((article) => (
              <a
                key={article.id}
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-start gap-2 rounded-md px-2 py-2 transition-colors hover:bg-secondary/30 active:bg-secondary/50"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] sm:text-sm leading-snug text-foreground/90">
                    {article.title}
                  </p>
                  <div className="mt-1 flex items-center gap-2 text-[11px] sm:text-xs text-muted-foreground">
                    {article.publisher && <span>{article.publisher}</span>}
                    {article.published_at && (
                      <span>{formatRelativeTime(article.published_at)}</span>
                    )}
                    {article.similarity_score < 1 && (
                      <span className="tabular-nums">
                        유사도 {Math.round(article.similarity_score * 100)}%
                      </span>
                    )}
                  </div>
                </div>
                <ExternalLink className="mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Comparison View ── */

function ComparisonView({
  comparison,
  isLoading,
  error,
}: {
  comparison: TrendComparison | null
  isLoading: boolean
  error: string | null
}) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
        {error}
      </div>
    )
  }

  if (!comparison) {
    return (
      <EmptyState
        icon={<Sparkles className="h-10 w-10" />}
        title="비교 데이터를 불러오는 중입니다"
        description="잠시만 기다려주세요."
      />
    )
  }

  const periodLabel = (p: string) => {
    if (p === '24h') return '24시간'
    if (p === '7d') return '7일'
    if (p === '30d') return '30일'
    return p
  }

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="rounded-lg border border-border/50 bg-secondary/20 p-4">
        <div className="mb-3 flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <Sparkles className="h-4 w-4" />
          비교 요약: {periodLabel(comparison.period_a)} vs {periodLabel(comparison.period_b)}
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <div className="text-xs text-muted-foreground">
              {periodLabel(comparison.period_a)} 기사
            </div>
            <div className="text-xl font-bold">{comparison.summary.total_a}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">
              {periodLabel(comparison.period_b)} 기사
            </div>
            <div className="text-xl font-bold">{comparison.summary.total_b}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">
              {periodLabel(comparison.period_a)} 토픽
            </div>
            <div className="text-xl font-bold">{comparison.summary.clusters_a}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">
              {periodLabel(comparison.period_b)} 토픽
            </div>
            <div className="text-xl font-bold">{comparison.summary.clusters_b}</div>
          </div>
        </div>
      </div>

      {/* Category Changes */}
      {Object.keys(comparison.category_changes).length > 0 && (
        <div>
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <Layers className="h-4 w-4" />
            카테고리별 변화
          </h3>
          <div className="space-y-2">
            {Object.entries(comparison.category_changes)
              .sort(([, a], [, b]) => Math.abs(b.change) - Math.abs(a.change))
              .map(([cat, data]) => {
                const isGrowth = data.change > 0
                const isDecline = data.change < 0
                return (
                  <div
                    key={cat}
                    className="flex items-center justify-between rounded-lg border border-border/50 bg-secondary/10 p-3"
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded px-2 py-1 text-xs font-medium ${CATEGORY_BG[cat] || 'bg-muted text-muted-foreground'}`}
                      >
                        {CATEGORY_LABELS[cat] || cat}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        {data.period_a}건 → {data.period_b}건
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {isGrowth && (
                        <ArrowUpRight className="h-4 w-4 text-green-500" />
                      )}
                      {isDecline && (
                        <ArrowDownRight className="h-4 w-4 text-red-500" />
                      )}
                      <span
                        className={`text-sm font-medium ${
                          isGrowth
                            ? 'text-green-500'
                            : isDecline
                              ? 'text-red-500'
                              : 'text-muted-foreground'
                        }`}
                      >
                        {data.change > 0 && '+'}
                        {data.change}건 ({data.change_pct > 0 && '+'}
                        {data.change_pct}%)
                      </span>
                    </div>
                  </div>
                )
              })}
          </div>
        </div>
      )}

      {/* New Topics */}
      {comparison.new_topics.length > 0 && (
        <div>
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <TrendingUp className="h-4 w-4 text-lifecycle-explosion" />
            신규 토픽 ({periodLabel(comparison.period_a)}에만 존재)
          </h3>
          <div className="space-y-2">
            {comparison.new_topics.map((topic, i) => (
              <div
                key={i}
                className="rounded-lg border border-border/50 bg-secondary/10 p-3"
              >
                <div className="mb-2 flex items-start justify-between gap-2">
                  <p className="flex-1 text-sm font-medium leading-snug">
                    {truncate(topic.title, 80)}
                  </p>
                  <span className="shrink-0 text-xs font-medium text-muted-foreground">
                    {topic.article_count}건
                  </span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {topic.categories.map((cat) => (
                    <span
                      key={cat}
                      className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${CATEGORY_BG[cat] || 'bg-muted text-muted-foreground'}`}
                    >
                      {CATEGORY_LABELS[cat] || cat}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Growing Topics */}
      {comparison.growing_topics.length > 0 && (
        <div>
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <Flame className="h-4 w-4 text-lifecycle-explosion" />
            성장 토픽 (성장률 상위)
          </h3>
          <div className="space-y-2">
            {comparison.growing_topics.map((topic, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-lg border border-border/50 bg-secondary/10 p-3"
              >
                <div className="flex-1">
                  <p className="text-sm font-medium leading-snug">
                    {truncate(topic.title, 70)}
                  </p>
                  <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{topic.article_count}건</span>
                  </div>
                </div>
                <div className="ml-2 text-right">
                  <div className="text-sm font-bold text-lifecycle-explosion">
                    {topic.growth_rate.toFixed(1)}
                  </div>
                  <div className="text-[10px] text-muted-foreground">건/시간</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Loading Skeleton ── */

function LoadingSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_340px]">
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-32" />
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3 rounded-lg p-3">
                  <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
                  <div className="flex-1 space-y-1.5">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-24" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-[200px] w-full rounded" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-24" />
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-6 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
