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
} from 'lucide-react'
import ReactECharts from 'echarts-for-react'
import echarts from '@/lib/echarts'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { fetchStats } from '@/services/adminApi'

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

export default function StatsPage() {
  const [data, setData] = useState<StatsData | null>(null)
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

  const articlesByDate = data?.articles_by_date ?? []

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
      const { data: res } = await fetchStats()
      setData(res)
      setError(null)
    } catch (err) {
      console.error('Stats fetch error:', err)
      setError('통계 데이터를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          통계
        </h2>
        <LoadingSkeleton />
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          통계
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

  if (!data) return null

  const statCards = [
    {
      label: '총 기사',
      value: data.overview.total_articles.toLocaleString('ko-KR'),
      icon: Newspaper,
      iconColor: 'text-blue-500',
      iconBg: 'bg-blue-50 dark:bg-blue-900/20',
    },
    {
      label: '총 언론사',
      value: data.overview.total_publishers.toLocaleString('ko-KR'),
      icon: Building2,
      iconColor: 'text-emerald-500',
      iconBg: 'bg-emerald-50 dark:bg-emerald-900/20',
    },
    {
      label: '추적 요청',
      value: data.overview.total_tracking.toLocaleString('ko-KR'),
      icon: Crosshair,
      iconColor: 'text-purple-500',
      iconBg: 'bg-purple-50 dark:bg-purple-900/20',
    },
    {
      label: '검색 쿼리',
      value: data.overview.total_searches.toLocaleString('ko-KR'),
      icon: Search,
      iconColor: 'text-amber-500',
      iconBg: 'bg-amber-50 dark:bg-amber-900/20',
    },
  ]

  const maxCategoryCount = Math.max(
    ...data.articles_by_category.map((c) => c.count),
    1
  )
  const maxPublisherCount = Math.max(
    ...data.top_publishers.map((p) => p.count),
    1
  )
  const trackingTotal =
    data.tracking_by_type.instant + data.tracking_by_type.live || 1
  const instantPercent = (data.tracking_by_type.instant / trackingTotal) * 100
  const livePercent = (data.tracking_by_type.live / trackingTotal) * 100

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          통계
        </h2>
        <button
          onClick={loadData}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          새로고침
        </button>
      </div>

      {/* Top: Stat Cards */}
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

      {/* Articles by Date Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-blue-500" />
            일별 기사 수집 추이 (30일)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.articles_by_date.length > 0 ? (
            <ReactECharts echarts={echarts} notMerge theme={chartTheme} option={articlesByDateOption} style={{ height: 200 }} />
          ) : (
            <p className="py-8 text-center text-sm text-gray-400">
              데이터 없음
            </p>
          )}
        </CardContent>
      </Card>

      {/* Category + Publisher Side by Side */}
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
              {data.articles_by_category.map((cat) => (
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
              {data.articles_by_category.length === 0 && (
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
              {data.top_publishers.map((pub, idx) => (
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
              {data.top_publishers.length === 0 && (
                <p className="py-4 text-center text-sm text-gray-400">
                  데이터 없음
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tracking Type Breakdown */}
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
                    {data.tracking_by_type.instant.toLocaleString('ko-KR')}건
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
                    {data.tracking_by_type.live.toLocaleString('ko-KR')}건
                  </p>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
