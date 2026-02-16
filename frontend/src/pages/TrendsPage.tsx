import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  TrendingUp,
  Newspaper,
  Flame,
  BarChart3,
  Clock,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Users,
  Layers,
  LayoutGrid,
  List,
  X,
} from 'lucide-react'
import ReactECharts from 'echarts-for-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { useTrendStore } from '@/stores/useTrendStore'
import { useTrackingStore } from '@/stores/useTrackingStore'
import { usePageTitle } from '@/hooks/usePageTitle'
import { formatRelativeTime, truncate } from '@/lib/utils'
import { CATEGORY_KEYS, CATEGORY_LABELS, CATEGORY_COLORS, CATEGORY_BG } from '@/lib/constants'
import type { TopicCluster, ClusterArticle } from '@/types'

export default function TrendsPage() {
  usePageTitle('트렌드')
  const navigate = useNavigate()
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

  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)

  const filteredClusters = useMemo(() => {
    const clusters = articleTrends?.clusters ?? []
    if (!selectedCategory) return clusters
    return clusters.filter((c) => c.categories.includes(selectedCategory))
  }, [articleTrends, selectedCategory])

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
  const handleSetTrendView = useCallback((view: 'overall' | 'category') => {
    setSelectedCategory(null)
    setTrendView(view)
  }, [setTrendView])

  const handleSetPeriod = useCallback((p: '24h' | '7d' | '30d') => {
    setSelectedCategory(null)
    setPeriod(p)
  }, [setPeriod])

  const handleTrack = async (article: ClusterArticle) => {
    useTrackingStore.getState().reset()
    await useTrackingStore.getState().selectCandidate({
      url: article.url,
      title: article.title,
      publisher: article.publisher ?? undefined,
      published_at: article.published_at ?? undefined,
    })
    navigate('/')
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

      {isLoading ? (
        <LoadingSkeleton />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_340px]">
          {/* Left: Main Content */}
          <div className="space-y-6">
            {/* Topic Clusters */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <Flame className="h-4 w-4 text-lifecycle-explosion" />
                    트렌딩 토픽
                  </CardTitle>
                  {/* View Toggle */}
                  <div className="inline-flex items-center rounded-lg border border-border bg-secondary/50 p-1">
                    <button
                      onClick={() => handleSetTrendView('overall')}
                      className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
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
                      className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                        trendView === 'category'
                          ? 'bg-background text-foreground shadow-sm'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      <LayoutGrid className="h-3.5 w-3.5" />
                      카테고리별
                    </button>
                  </div>
                </div>
                {selectedCategory && (
                  <div className="mt-3 flex items-center gap-2">
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-medium ${CATEGORY_BG[selectedCategory] || 'bg-muted text-muted-foreground'}`}
                    >
                      {CATEGORY_LABELS[selectedCategory] || selectedCategory}
                    </span>
                    <span className="text-xs text-muted-foreground">필터 적용중</span>
                    <button
                      onClick={() => setSelectedCategory(null)}
                      className="rounded-md p-0.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
              </CardHeader>
              <CardContent>
                {!articleTrends || filteredClusters.length === 0 ? (
                  <div className="py-12 text-center">
                    <Newspaper className="mx-auto mb-3 h-10 w-10 text-muted-foreground/40" />
                    <p className="text-muted-foreground">
                      더 많은 기사가 수집되면 트렌드가 나타납니다.
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground/60">
                      30분마다 자동으로 기사를 수집합니다.
                    </p>
                  </div>
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
                            />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Hourly Activity Chart */}
            {articleTrends && articleTrends.hourly_counts.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-lifecycle-spread" />
                    시간대별 수집량
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ReactECharts
                    notMerge
                    option={{
                      backgroundColor: 'transparent',
                      tooltip: {
                        trigger: 'axis',
                        backgroundColor: '#1f2937',
                        borderColor: '#374151',
                        textStyle: { color: '#e5e7eb', fontSize: 12 },
                        formatter: (params: any) => {
                          const p = params[0]
                          const d = new Date(p.name)
                          const label = d.toLocaleString('ko-KR', {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })
                          return `${label}<br/>${p.value}건`
                        },
                      },
                      grid: { left: 10, right: 10, top: 10, bottom: 30, containLabel: true },
                      xAxis: {
                        type: 'category',
                        data: articleTrends.hourly_counts.map((h) => h.hour),
                        axisLabel: {
                          color: '#9ca3af',
                          fontSize: 10,
                          formatter: (v: string) => {
                            const d = new Date(v)
                            return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}시`
                          },
                          rotate: 25,
                          interval: 0,
                        },
                        axisLine: { lineStyle: { color: '#374151' } },
                      },
                      yAxis: {
                        type: 'value',
                        axisLabel: { color: '#9ca3af', fontSize: 10 },
                        splitLine: { lineStyle: { color: '#1f2937' } },
                      },
                      series: [
                        {
                          type: 'bar',
                          data: articleTrends.hourly_counts.map((h) => h.count),
                          itemStyle: {
                            color: {
                              type: 'linear',
                              x: 0, y: 0, x2: 0, y2: 1,
                              colorStops: [
                                { offset: 0, color: '#3b82f6' },
                                { offset: 1, color: '#1e3a5f' },
                              ],
                            },
                            borderRadius: [4, 4, 0, 0],
                          },
                          barWidth: '60%',
                        },
                      ],
                    }}
                    style={{ height: 220 }}
                    theme="dark"
                  />
                </CardContent>
              </Card>
            )}
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
                    notMerge
                    option={{
                      backgroundColor: 'transparent',
                      tooltip: {
                        backgroundColor: '#1f2937',
                        borderColor: '#374151',
                        textStyle: { color: '#e5e7eb', fontSize: 12 },
                        formatter: (params: any) =>
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
                                opacity: selectedCategory && selectedCategory !== cat ? 0.3 : 1,
                              },
                            }),
                          ),
                        },
                      ],
                    }}
                    style={{ height: 220, cursor: 'pointer' }}
                    theme="dark"
                    onEvents={{
                      click: (params: any) => {
                        const catKey = Object.entries(CATEGORY_LABELS).find(
                          ([, label]) => label === params.name,
                        )?.[0]
                        if (catKey) {
                          const isDeselect = selectedCategory === catKey
                          setSelectedCategory(isDeselect ? null : catKey)
                          if (!isDeselect && trendView !== 'overall') {
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
}: {
  cluster: TopicCluster
  rank: number
  isExpanded: boolean
  onToggle: () => void
  onTrack: (article: ClusterArticle) => void
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
            className="mb-3 flex w-full items-center justify-center gap-2 rounded-lg border border-lifecycle-origin/30 bg-lifecycle-origin/10 px-4 py-2.5 text-sm font-medium text-lifecycle-origin transition-colors hover:bg-lifecycle-origin/20 active:scale-[0.98]"
          >
            <Newspaper className="h-4 w-4" />
            이 토픽의 대표 기사 추적 시작
          </button>
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
