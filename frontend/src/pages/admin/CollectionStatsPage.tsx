import { useState, useEffect, useMemo } from 'react'
import {
  BarChart3,
  Newspaper,
  Building2,
  Search,
  Crosshair,
  RefreshCw,
  Tag,
  Zap,
  Radio,
  Rss,
  Clock,
  Globe,
} from 'lucide-react'
import ReactECharts from 'echarts-for-react'
import echarts from '@/lib/echarts'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { fetchCrawl, fetchStats } from '@/services/adminApi'

interface CrawlData {
  schedule: {
    interval_minutes: number
    categories: string[]
  }
  feed_sources?: {
    categories: Array<{ key: string; label: string; url: string }>
    publishers: Array<{ name: string; url: string }>
    limits: {
      per_category: number
      per_publisher: number
      max_per_run: number
    }
  }
  category_stats: Array<{ category: string; count: number }>
  publisher_stats: Array<{ publisher: string; count: number }>
  recent_articles: Array<{
    title: string
    publisher: string
    category: string
    created_at: string
  }>
  daily_counts: Array<{ date: string; count: number }>
}

interface StatsData {
  overview: {
    total_articles: number
    total_publishers: number
    total_tracking: number
    total_searches: number
  }
  articles_by_date: Array<{ date: string; count: number }>
  articles_by_category: Array<{ category: string; count: number }>
  top_publishers: Array<{ publisher: string; count: number }>
  tracking_by_type: {
    instant: number
    live: number
  }
}

const CATEGORY_LABELS: Record<string, string> = {
  headlines: '헤드라인',
  politics: '정치',
  economy: '경제',
  society: '사회',
  tech: '기술',
  entertainment: '연예',
  world: '세계',
  sports: '스포츠',
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800"
          />
        ))}
      </div>
      <div className="h-48 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="h-64 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
        <div className="h-64 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
      </div>
    </div>
  )
}

export default function CollectionStatsPage() {
  const [crawlData, setCrawlData] = useState<CrawlData | null>(null)
  const [statsData, setStatsData] = useState<StatsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // --- Theme (before early returns for useMemo) ---
  const isDark = document.documentElement.classList.contains('dark')
  const textColor = isDark ? '#9CA3AF' : '#6B7280'
  const gridLineColor = isDark ? 'rgba(55,65,81,0.3)' : 'rgba(229,231,235,0.6)'
  const tooltipBg = isDark ? '#1F2937' : '#FFF'
  const tooltipBorder = isDark ? '#374151' : '#E5E7EB'
  const tooltipText = isDark ? '#E5E7EB' : '#111827'
  const chartTheme = isDark ? 'dark-transparent' : undefined

  const articlesByDate = statsData?.articles_by_date ?? []

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const articlesByDateOption = useMemo(() => ({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: tooltipBg,
      borderColor: tooltipBorder,
      textStyle: { color: tooltipText, fontSize: 12 },
      formatter: (params: Array<{ name: string; value: number }>) => {
        const p = params[0]
        return `${p.name}: ${p.value.toLocaleString('ko-KR')}건`
      },
    },
    grid: { left: 48, right: 20, top: 16, bottom: 36 },
    xAxis: {
      type: 'category' as const,
      boundaryGap: false,
      data: articlesByDate.map((d) => d.date.slice(5)),
      axisLabel: { color: textColor, fontSize: 11 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: { color: textColor, fontSize: 10 },
      splitLine: { lineStyle: { color: gridLineColor, type: 'dashed' as const } },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'line',
        smooth: 0.4,
        showSymbol: false,
        data: articlesByDate.map((d) => d.count),
        areaStyle: {
          color: {
            type: 'linear' as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: isDark ? 'rgba(99,102,241,0.35)' : 'rgba(99,102,241,0.18)' },
              { offset: 1, color: 'rgba(99,102,241,0.01)' },
            ],
          },
        },
        lineStyle: { color: '#6366F1', width: 2 },
        itemStyle: { color: '#6366F1' },
      },
    ],
  }), [articlesByDate, isDark, textColor, gridLineColor, tooltipBg, tooltipBorder, tooltipText])

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const [crawlRes, statsRes] = await Promise.all([
        fetchCrawl(),
        fetchStats(),
      ])
      setCrawlData(crawlRes.data)
      setStatsData(statsRes.data)
      setError(null)
    } catch (err) {
      console.error('CollectionStats fetch error:', err)
      setError('데이터를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          수집 통계
        </h2>
        <LoadingSkeleton />
      </div>
    )
  }

  if (error && !statsData && !crawlData) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          수집 통계
        </h2>
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-gray-500 dark:text-gray-400">{error}</p>
            <button
              onClick={loadData}
              className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
            >
              <RefreshCw className="h-4 w-4" />
              다시 시도
            </button>
          </CardContent>
        </Card>
      </div>
    )
  }

  const statCards = statsData
    ? [
        {
          label: '총 기사',
          value: statsData.overview.total_articles.toLocaleString('ko-KR'),
          icon: Newspaper,
          iconColor: 'text-blue-500',
          iconBg: 'bg-blue-50 dark:bg-blue-900/20',
        },
        {
          label: '총 언론사',
          value: statsData.overview.total_publishers.toLocaleString('ko-KR'),
          icon: Building2,
          iconColor: 'text-emerald-500',
          iconBg: 'bg-emerald-50 dark:bg-emerald-900/20',
        },
        {
          label: '추적 요청',
          value: statsData.overview.total_tracking.toLocaleString('ko-KR'),
          icon: Crosshair,
          iconColor: 'text-purple-500',
          iconBg: 'bg-purple-50 dark:bg-purple-900/20',
        },
        {
          label: '검색 쿼리',
          value: statsData.overview.total_searches.toLocaleString('ko-KR'),
          icon: Search,
          iconColor: 'text-amber-500',
          iconBg: 'bg-amber-50 dark:bg-amber-900/20',
        },
      ]
    : []

  const maxCategoryCount = Math.max(
    ...(statsData?.articles_by_category.map((c) => c.count) ?? [1]),
    1
  )
  const maxPublisherCount = Math.max(
    ...(statsData?.top_publishers.map((p) => p.count) ?? [1]),
    1
  )
  const trackingTotal = statsData
    ? (statsData.tracking_by_type.instant + statsData.tracking_by_type.live) || 1
    : 1
  const instantPercent = statsData ? (statsData.tracking_by_type.instant / trackingTotal) * 100 : 0
  const livePercent = statsData ? (statsData.tracking_by_type.live / trackingTotal) * 100 : 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          수집 통계
        </h2>
        <button
          onClick={loadData}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          새로고침
        </button>
      </div>

      {/* Overview Stat Cards */}
      {statCards.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {statCards.map((card) => (
            <Card key={card.label}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {card.label}
                    </p>
                    <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-gray-100">
                      {card.value}
                    </p>
                  </div>
                  <div
                    className={`flex h-12 w-12 items-center justify-center rounded-xl ${card.iconBg}`}
                  >
                    <card.icon className={`h-6 w-6 ${card.iconColor}`} />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Schedule Info */}
      {crawlData && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-blue-500" />
              수집 스케줄
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center gap-4">
              <div>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  수집 주기:
                </span>
                <span className="ml-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
                  {crawlData.schedule.interval_minutes}분
                </span>
              </div>
              <div className="h-4 w-px bg-gray-200 dark:bg-gray-700" />
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  카테고리:
                </span>
                {crawlData.schedule.categories.map((cat) => (
                  <span
                    key={cat}
                    className="inline-flex rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                  >
                    {CATEGORY_LABELS[cat] || cat}
                  </span>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Articles by Date Chart (30 days) */}
      {statsData && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-blue-500" />
              일별 기사 수집 추이 (30일)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {statsData.articles_by_date.length > 0 ? (
              <ReactECharts echarts={echarts} notMerge theme={chartTheme} option={articlesByDateOption} style={{ height: 200 }} />
            ) : (
              <p className="py-8 text-center text-sm text-gray-400">
                데이터 없음
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Category + Publisher Side by Side */}
      {statsData && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Category Distribution */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Tag className="h-5 w-5 text-purple-500" />
                카테고리 분포
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {statsData.articles_by_category.map((cat) => (
                  <div key={cat.category}>
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-sm text-gray-700 dark:text-gray-300">
                        {CATEGORY_LABELS[cat.category] || cat.category}
                      </span>
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {cat.count.toLocaleString('ko-KR')}건
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                      <div
                        className="h-full rounded-full bg-purple-500 transition-all duration-500"
                        style={{
                          width: `${(cat.count / maxCategoryCount) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
                {statsData.articles_by_category.length === 0 && (
                  <p className="py-4 text-center text-sm text-gray-400">
                    데이터 없음
                  </p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Publisher Ranking */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-5 w-5 text-emerald-500" />
                언론사 순위 (Top 15)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {statsData.top_publishers.map((pub, idx) => (
                  <div key={pub.publisher} className="flex items-center gap-3">
                    <span
                      className={`w-6 text-right text-xs font-bold ${
                        idx < 3
                          ? 'text-blue-500'
                          : 'text-gray-400 dark:text-gray-500'
                      }`}
                    >
                      {idx + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="mb-0.5 flex items-center justify-between">
                        <span className="truncate text-sm text-gray-700 dark:text-gray-300">
                          {pub.publisher}
                        </span>
                        <span className="ml-2 shrink-0 text-xs font-medium text-gray-500 dark:text-gray-400">
                          {pub.count.toLocaleString('ko-KR')}건
                        </span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                        <div
                          className="h-full rounded-full bg-emerald-500 transition-all duration-500"
                          style={{
                            width: `${(pub.count / maxPublisherCount) * 100}%`,
                          }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
                {statsData.top_publishers.length === 0 && (
                  <p className="py-4 text-center text-sm text-gray-400">
                    데이터 없음
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Feed Sources */}
      {crawlData?.feed_sources && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Category Feeds */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Globe className="h-5 w-5 text-blue-500" />
                카테고리 피드
                <span className="ml-auto text-xs font-normal text-gray-400">
                  피드당 최대 {crawlData.feed_sources.limits.per_category}건
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {crawlData.feed_sources.categories.map((feed) => (
                  <div
                    key={feed.key}
                    className="flex items-center justify-between gap-3 rounded-lg border border-gray-100 px-3 py-2 dark:border-gray-800"
                  >
                    <span className="shrink-0 text-sm font-medium text-gray-900 dark:text-gray-100">
                      {feed.label}
                    </span>
                    <span
                      className="min-w-0 truncate text-xs text-gray-400"
                      title={feed.url}
                    >
                      {feed.url}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Publisher Feeds */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-5 w-5 text-emerald-500" />
                언론사 피드
                <span className="ml-auto text-xs font-normal text-gray-400">
                  피드당 최대 {crawlData.feed_sources.limits.per_publisher}건
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {crawlData.feed_sources.publishers.map((pub) => (
                  <div
                    key={pub.name}
                    className="flex items-center justify-between gap-3 rounded-lg border border-gray-100 px-3 py-2 dark:border-gray-800"
                  >
                    <span className="shrink-0 text-sm font-medium text-gray-900 dark:text-gray-100">
                      {pub.name}
                    </span>
                    <span
                      className="min-w-0 truncate text-xs text-gray-400"
                      title={pub.url}
                    >
                      {pub.url}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tracking Type Breakdown */}
      {statsData && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Crosshair className="h-5 w-5 text-blue-500" />
              추적 유형 분포
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Stacked bar */}
              <div className="h-6 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                <div className="flex h-full">
                  <div
                    className="flex items-center justify-center bg-blue-500 text-xs font-medium text-white transition-all duration-500"
                    style={{ width: `${instantPercent}%` }}
                  >
                    {instantPercent > 10 ? `${instantPercent.toFixed(0)}%` : ''}
                  </div>
                  <div
                    className="flex items-center justify-center bg-amber-500 text-xs font-medium text-white transition-all duration-500"
                    style={{ width: `${livePercent}%` }}
                  >
                    {livePercent > 10 ? `${livePercent.toFixed(0)}%` : ''}
                  </div>
                </div>
              </div>

              {/* Legend */}
              <div className="flex flex-wrap gap-6">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 dark:bg-blue-900/20">
                    <Zap className="h-4 w-4 text-blue-500" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      즉시 추적 (Instant)
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {statsData.tracking_by_type.instant.toLocaleString('ko-KR')}건
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-50 dark:bg-amber-900/20">
                    <Radio className="h-4 w-4 text-amber-500" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      라이브 추적 (Live)
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {statsData.tracking_by_type.live.toLocaleString('ko-KR')}건
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Articles Table */}
      {crawlData && crawlData.recent_articles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Rss className="h-5 w-5 text-amber-500" />
              최근 수집 기사
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="pb-3 pr-4 text-left font-medium text-gray-500 dark:text-gray-400">
                      제목
                    </th>
                    <th className="pb-3 pr-4 text-left font-medium text-gray-500 dark:text-gray-400">
                      언론사
                    </th>
                    <th className="pb-3 pr-4 text-left font-medium text-gray-500 dark:text-gray-400">
                      카테고리
                    </th>
                    <th className="pb-3 text-left font-medium text-gray-500 dark:text-gray-400">
                      수집 시각
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {crawlData.recent_articles.map((article, idx) => (
                    <tr key={idx} className="group">
                      <td className="max-w-xs truncate py-2.5 pr-4 text-gray-900 dark:text-gray-100">
                        {article.title}
                      </td>
                      <td className="whitespace-nowrap py-2.5 pr-4 text-gray-500 dark:text-gray-400">
                        {article.publisher}
                      </td>
                      <td className="py-2.5 pr-4">
                        <span className="inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                          {CATEGORY_LABELS[article.category] || article.category}
                        </span>
                      </td>
                      <td className="whitespace-nowrap py-2.5 text-xs text-gray-400">
                        {new Date(article.created_at).toLocaleString('ko-KR')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
