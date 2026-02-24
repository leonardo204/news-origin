import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import {
  Activity,
  Clock,
  AlertTriangle,
  Globe,
  RefreshCw,
  TrendingUp,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { fetchTraffic } from '@/services/adminApi'
import ReactECharts from 'echarts-for-react'
import echarts from '@/lib/echarts'

// --- Types ---

interface TrafficSummary {
  today: number
  week: number
  month: number
  avg_duration: number
  error_rate: number
  unique_ips: number
}

interface HourlyEntry {
  hour: string
  count: number
  avg_duration: number
}

interface DailyEntry {
  date: string
  count: number
  avg_duration: number
  errors: number
}

interface StatusEntry {
  status_code: number
  count: number
}

interface EndpointEntry {
  method: string
  path: string
  count: number
  avg_duration: number
  max_duration?: number
}

interface ErrorEntry {
  method: string
  path: string
  status_code: number
  duration_ms: number
  client_ip: string | null
  created_at: string | null
}

interface GeoCity {
  city: string
  count: number
  unique_ips: number
}

interface GeoEntry {
  country: string
  countryCode: string
  count: number
  unique_ips: number
  cities: GeoCity[]
}

interface TrafficData {
  summary: TrafficSummary
  hourly: HourlyEntry[]
  daily: DailyEntry[]
  status_distribution: StatusEntry[]
  top_by_count: EndpointEntry[]
  top_by_duration: EndpointEntry[]
  recent_errors: ErrorEntry[]
  geo_distribution: GeoEntry[]
}

// --- Helpers ---

function formatDuration(ms: number) {
  if (ms < 1) return '<1ms'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function statusColor(code: number) {
  if (code < 300) return 'text-emerald-600 dark:text-emerald-400'
  if (code < 400) return 'text-blue-600 dark:text-blue-400'
  if (code < 500) return 'text-amber-600 dark:text-amber-400'
  return 'text-red-600 dark:text-red-400'
}

function statusBadgeBg(code: number) {
  if (code < 300) return 'bg-emerald-50 dark:bg-emerald-900/20'
  if (code < 400) return 'bg-blue-50 dark:bg-blue-900/20'
  if (code < 500) return 'bg-amber-50 dark:bg-amber-900/20'
  return 'bg-red-50 dark:bg-red-900/20'
}

function formatTime(isoStr: string | null) {
  if (!isoStr) return '-'
  const d = new Date(isoStr)
  return d.toLocaleString('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function countryFlag(code: string): string {
  if (!code || code.length !== 2) return ''
  const offset = 0x1f1e6
  return String.fromCodePoint(
    offset + code.charCodeAt(0) - 65,
    offset + code.charCodeAt(1) - 65,
  )
}

// --- Skeleton ---

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
        ))}
      </div>
      <div className="h-64 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="h-64 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
        <div className="h-64 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
      </div>
    </div>
  )
}

// --- Component ---

export default function TrafficPage() {
  const [data, setData] = useState<TrafficData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedGeo, setExpandedGeo] = useState<Set<string>>(new Set())
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // --- Theme (before early returns for useMemo) ---
  const isDark = document.documentElement.classList.contains('dark')
  const textColor = isDark ? '#9CA3AF' : '#6B7280'
  const gridLineColor = isDark ? 'rgba(55, 65, 81, 0.3)' : 'rgba(229, 231, 235, 0.6)'
  const tooltipBg = isDark ? '#1F2937' : '#FFF'
  const tooltipBorder = isDark ? '#374151' : '#E5E7EB'
  const tooltipText = isDark ? '#E5E7EB' : '#111827'
  const chartTheme = isDark ? ('dark-transparent' as const) : undefined

  // --- Daily chart (useMemo — rebuilt from scratch) ---
  const dailyEntries = data?.daily ?? []

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const dailyOption = useMemo(() => ({
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: tooltipBg,
      borderColor: tooltipBorder,
      textStyle: { color: tooltipText, fontSize: 12 },
    },
    legend: {
      data: ['요청수', '에러'],
      textStyle: { color: textColor, fontSize: 11 },
      right: 16,
      top: 0,
    },
    grid: { left: 48, right: 20, top: 28, bottom: 56 },
    dataZoom: [
      {
        type: 'slider' as const,
        show: true,
        height: 18,
        bottom: 4,
        borderColor: 'transparent',
        backgroundColor: isDark ? 'rgba(55,65,81,0.3)' : 'rgba(229,231,235,0.5)',
        fillerColor: isDark ? 'rgba(99,102,241,0.2)' : 'rgba(99,102,241,0.12)',
        handleStyle: { color: '#6366F1', borderColor: '#6366F1' },
        textStyle: { color: textColor, fontSize: 10 },
        dataBackground: {
          lineStyle: { color: 'rgba(99,102,241,0.3)' },
          areaStyle: { color: 'rgba(99,102,241,0.08)' },
        },
        selectedDataBackground: {
          lineStyle: { color: '#6366F1' },
          areaStyle: { color: 'rgba(99,102,241,0.15)' },
        },
      },
      { type: 'inside' as const },
    ],
    xAxis: {
      type: 'category' as const,
      boundaryGap: false,
      data: dailyEntries.map((d) => d.date.slice(5)),
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
        name: '요청수',
        type: 'line',
        smooth: 0.4,
        showSymbol: false,
        data: dailyEntries.map((d) => d.count),
        areaStyle: {
          color: {
            type: 'linear' as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: isDark ? 'rgba(99,102,241,0.35)' : 'rgba(99,102,241,0.2)' },
              { offset: 1, color: 'rgba(99,102,241,0.02)' },
            ],
          },
        },
        lineStyle: { color: '#6366F1', width: 2 },
        itemStyle: { color: '#6366F1' },
      },
      {
        name: '에러',
        type: 'line',
        smooth: 0.4,
        showSymbol: false,
        data: dailyEntries.map((d) => d.errors),
        lineStyle: { color: '#EF4444', width: 1.5 },
        itemStyle: { color: '#EF4444' },
      },
    ],
  }), [dailyEntries, isDark, textColor, gridLineColor, tooltipBg, tooltipBorder, tooltipText])

  const loadData = useCallback(async () => {
    try {
      const { data: res } = await fetchTraffic({ period: '30d' })
      setData(res)
      setError(null)
    } catch (err) {
      console.error('Traffic fetch error:', err)
      setError('트래픽 데이터를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
    intervalRef.current = setInterval(() => loadData(), 30000)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [loadData])

  if (loading && !data) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">트래픽</h2>
        <LoadingSkeleton />
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">트래픽</h2>
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-gray-500 dark:text-gray-400">{error}</p>
            <button
              onClick={() => loadData()}
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

  const { summary } = data

  // --- Hourly chart (area + line dual axis) ---
  const hourlyOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: tooltipBg,
      borderColor: tooltipBorder,
      textStyle: { color: tooltipText, fontSize: 12 },
    },
    grid: { left: 48, right: 48, top: 24, bottom: 36 },
    xAxis: {
      type: 'category' as const,
      boundaryGap: false,
      data: data.hourly.map((h) => {
        const d = new Date(h.hour)
        return `${d.getHours().toString().padStart(2, '0')}:00`
      }),
      axisLabel: { color: textColor, fontSize: 11 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: [
      {
        type: 'value' as const,
        name: '요청수',
        nameTextStyle: { color: textColor, fontSize: 10 },
        axisLabel: { color: textColor, fontSize: 10 },
        splitLine: { lineStyle: { color: gridLineColor, type: 'dashed' as const } },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      {
        type: 'value' as const,
        name: 'ms',
        nameTextStyle: { color: textColor, fontSize: 10 },
        axisLabel: { color: textColor, fontSize: 10 },
        splitLine: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
      },
    ],
    series: [
      {
        name: '요청수',
        type: 'line',
        smooth: 0.4,
        showSymbol: false,
        data: data.hourly.map((h) => h.count),
        areaStyle: {
          color: {
            type: 'linear' as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: isDark ? 'rgba(99,102,241,0.35)' : 'rgba(99,102,241,0.2)' },
              { offset: 1, color: 'rgba(99,102,241,0.01)' },
            ],
          },
        },
        lineStyle: { color: '#6366F1', width: 2 },
        itemStyle: { color: '#6366F1' },
      },
      {
        name: '응답시간',
        type: 'line',
        yAxisIndex: 1,
        smooth: 0.4,
        showSymbol: false,
        data: data.hourly.map((h) => h.avg_duration),
        lineStyle: { color: '#F59E0B', width: 1.5, type: 'dashed' as const },
        itemStyle: { color: '#F59E0B' },
      },
    ],
  }

  // --- Status donut ---
  const STATUS_COLORS: Record<string, string> = {
    '2xx': '#10B981',
    '3xx': '#6366F1',
    '4xx': '#F59E0B',
    '5xx': '#EF4444',
  }

  const statusGroups: Record<string, number> = {}
  data.status_distribution.forEach((s) => {
    const group = `${Math.floor(s.status_code / 100)}xx`
    statusGroups[group] = (statusGroups[group] || 0) + s.count
  })
  const statusTotal = Object.values(statusGroups).reduce((a, b) => a + b, 0)

  const donutOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: tooltipBg,
      borderColor: tooltipBorder,
      textStyle: { color: tooltipText, fontSize: 12 },
      formatter: '{b}: {c} ({d}%)',
    },
    graphic: statusTotal > 0 ? [{
      type: 'text' as const,
      left: 'center',
      top: '42%',
      style: {
        text: statusTotal.toLocaleString('ko-KR'),
        fill: isDark ? '#E5E7EB' : '#111827',
        fontSize: 20,
        fontWeight: 'bold' as const,
        textAlign: 'center' as const,
      },
    }, {
      type: 'text' as const,
      left: 'center',
      top: '55%',
      style: {
        text: '총 요청',
        fill: textColor,
        fontSize: 11,
        textAlign: 'center' as const,
      },
    }] : [],
    series: [
      {
        type: 'pie',
        radius: ['50%', '72%'],
        avoidLabelOverlap: true,
        label: { show: true, color: textColor, fontSize: 11, formatter: '{b}\n{d}%' },
        itemStyle: { borderRadius: 4, borderColor: isDark ? '#111827' : '#FFF', borderWidth: 2 },
        data: Object.entries(statusGroups).map(([group, count]) => ({
          name: group,
          value: count,
          itemStyle: { color: STATUS_COLORS[group] || '#9CA3AF' },
        })),
      },
    ],
  }

  // --- Cards ---
  const statCards = [
    {
      label: '오늘 요청',
      value: summary.today.toLocaleString('ko-KR'),
      sub: `이번 주 ${summary.week.toLocaleString('ko-KR')}`,
      icon: TrendingUp,
      iconColor: 'text-blue-500',
      iconBg: 'bg-blue-50 dark:bg-blue-900/20',
    },
    {
      label: '평균 응답시간',
      value: formatDuration(summary.avg_duration),
      sub: '선택 기간 기준',
      icon: Clock,
      iconColor: 'text-emerald-500',
      iconBg: 'bg-emerald-50 dark:bg-emerald-900/20',
    },
    {
      label: '에러율',
      value: `${summary.error_rate}%`,
      sub: '4xx + 5xx 비율',
      icon: AlertTriangle,
      iconColor: summary.error_rate > 5 ? 'text-red-500' : 'text-amber-500',
      iconBg: summary.error_rate > 5
        ? 'bg-red-50 dark:bg-red-900/20'
        : 'bg-amber-50 dark:bg-amber-900/20',
    },
    {
      label: '방문자',
      value: summary.unique_ips.toLocaleString('ko-KR'),
      sub: '고유 IP 기준',
      icon: Globe,
      iconColor: 'text-purple-500',
      iconBg: 'bg-purple-50 dark:bg-purple-900/20',
    },
  ]

  // Geo distribution
  const geo = data.geo_distribution || []
  const maxGeoCount = Math.max(...geo.map((g) => g.count), 1)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">트래픽</h2>
        <button
          onClick={() => loadData()}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          새로고침
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {statCards.map((card) => (
          <Card key={card.label}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{card.label}</p>
                  <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-gray-100">
                    {card.value}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">{card.sub}</p>
                </div>
                <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${card.iconBg}`}>
                  <card.icon className={`h-6 w-6 ${card.iconColor}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Hourly Traffic */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-blue-500" />
            시간별 트래픽
            <span className="text-xs font-normal text-gray-400">24h</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.hourly.length > 0 ? (
            <ReactECharts echarts={echarts} notMerge theme={chartTheme} option={hourlyOption} style={{ height: 260 }} />
          ) : (
            <p className="py-16 text-center text-sm text-gray-400">데이터가 쌓이면 여기에 시간별 추이가 표시됩니다</p>
          )}
        </CardContent>
      </Card>

      {/* Daily Traffic */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-blue-500" />
            일별 트래픽
            <span className="text-xs font-normal text-gray-400">30일</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.daily.length > 0 ? (
            <ReactECharts echarts={echarts} notMerge theme={chartTheme} option={dailyOption} style={{ height: 280 }} />
          ) : (
            <p className="py-16 text-center text-sm text-gray-400">데이터가 쌓이면 여기에 일별 추이가 표시됩니다</p>
          )}
        </CardContent>
      </Card>

      {/* Status + Geo side by side */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Status Donut */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              상태코드 분포
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.status_distribution.length > 0 ? (
              <ReactECharts echarts={echarts} notMerge theme={chartTheme} option={donutOption} style={{ height: 260 }} />
            ) : (
              <p className="py-12 text-center text-sm text-gray-400">데이터 없음</p>
            )}
          </CardContent>
        </Card>

        {/* Geo Distribution — Hierarchical */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-5 w-5 text-purple-500" />
              방문자 지역
            </CardTitle>
          </CardHeader>
          <CardContent>
            {geo.length > 0 ? (
              <div className="space-y-1">
                {geo.map((g) => {
                  const isExpanded = expandedGeo.has(g.country)
                  const hasCities = g.cities.length > 0
                  const maxCityCount = hasCities ? Math.max(...g.cities.map((c) => c.count), 1) : 1
                  return (
                    <div key={g.country}>
                      {/* Country row */}
                      <button
                        type="button"
                        className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50"
                        onClick={() => {
                          if (!hasCities) return
                          setExpandedGeo((prev) => {
                            const next = new Set(prev)
                            if (next.has(g.country)) next.delete(g.country)
                            else next.add(g.country)
                            return next
                          })
                        }}
                      >
                        {hasCities ? (
                          isExpanded ? (
                            <ChevronDown className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" />
                          ) : (
                            <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" />
                          )
                        ) : (
                          <span className="w-3.5 flex-shrink-0" />
                        )}
                        <span className="text-base leading-none">{countryFlag(g.countryCode)}</span>
                        <span className="flex-1 text-sm font-medium text-gray-700 dark:text-gray-300">
                          {g.country}
                        </span>
                        <span className="text-xs text-gray-400 dark:text-gray-500">
                          {g.unique_ips} IP
                        </span>
                        <span className="min-w-[4rem] text-right text-sm font-medium text-gray-900 dark:text-gray-100">
                          {g.count.toLocaleString('ko-KR')}건
                        </span>
                        <div className="ml-2 h-1.5 w-24 flex-shrink-0 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                          <div
                            className="h-full rounded-full bg-purple-500 transition-all duration-500"
                            style={{ width: `${(g.count / maxGeoCount) * 100}%` }}
                          />
                        </div>
                      </button>

                      {/* Expanded cities */}
                      {isExpanded && hasCities && (
                        <div className="mb-2 ml-9 space-y-0.5 border-l-2 border-purple-100 pl-3 dark:border-purple-900/50">
                          {g.cities.map((c) => (
                            <div key={c.city} className="flex items-center gap-2 py-1">
                              <span className="flex-1 text-xs text-gray-600 dark:text-gray-400">
                                {c.city}
                              </span>
                              <span className="text-[10px] text-gray-400 dark:text-gray-500">
                                {c.unique_ips} IP
                              </span>
                              <span className="min-w-[3.5rem] text-right text-xs font-medium text-gray-700 dark:text-gray-300">
                                {c.count.toLocaleString('ko-KR')}건
                              </span>
                              <div className="ml-1 h-1 w-16 flex-shrink-0 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                                <div
                                  className="h-full rounded-full bg-purple-300 dark:bg-purple-700 transition-all duration-500"
                                  style={{ width: `${(c.count / maxCityCount) * 100}%` }}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="py-12 text-center text-sm text-gray-400">지역 데이터 없음</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Top Endpoints */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-blue-500" />
            엔드포인트별 요청
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.top_by_count.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="pb-2 text-left font-medium text-gray-500 dark:text-gray-400">엔드포인트</th>
                    <th className="pb-2 text-right font-medium text-gray-500 dark:text-gray-400">요청수</th>
                    <th className="pb-2 text-right font-medium text-gray-500 dark:text-gray-400">평균 응답</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_by_count.map((ep, i) => (
                    <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
                      <td className="py-2">
                        <span className="mr-1.5 inline-block rounded bg-gray-100 px-1.5 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                          {ep.method}
                        </span>
                        <span className="text-gray-700 dark:text-gray-300">{ep.path}</span>
                      </td>
                      <td className="py-2 text-right font-medium text-gray-900 dark:text-gray-100">
                        {ep.count.toLocaleString('ko-KR')}
                      </td>
                      <td className="py-2 text-right text-gray-500 dark:text-gray-400">
                        {formatDuration(ep.avg_duration)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="py-12 text-center text-sm text-gray-400">데이터 없음</p>
          )}
        </CardContent>
      </Card>

      {/* Slow Endpoints */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-amber-500" />
            느린 엔드포인트
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.top_by_duration.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="pb-2 text-left font-medium text-gray-500 dark:text-gray-400">엔드포인트</th>
                    <th className="pb-2 text-right font-medium text-gray-500 dark:text-gray-400">요청수</th>
                    <th className="pb-2 text-right font-medium text-gray-500 dark:text-gray-400">평균</th>
                    <th className="pb-2 text-right font-medium text-gray-500 dark:text-gray-400">최대</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_by_duration.map((ep, i) => (
                    <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
                      <td className="py-2">
                        <span className="mr-1.5 inline-block rounded bg-gray-100 px-1.5 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                          {ep.method}
                        </span>
                        <span className="text-gray-700 dark:text-gray-300">{ep.path}</span>
                      </td>
                      <td className="py-2 text-right font-medium text-gray-900 dark:text-gray-100">
                        {ep.count.toLocaleString('ko-KR')}
                      </td>
                      <td className="py-2 text-right text-amber-600 dark:text-amber-400">
                        {formatDuration(ep.avg_duration)}
                      </td>
                      <td className="py-2 text-right text-red-600 dark:text-red-400">
                        {formatDuration(ep.max_duration || 0)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="py-12 text-center text-sm text-gray-400">데이터 없음</p>
          )}
        </CardContent>
      </Card>

      {/* Recent Errors */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            최근 에러
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.recent_errors.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="pb-2 text-left font-medium text-gray-500 dark:text-gray-400">시간</th>
                    <th className="pb-2 text-left font-medium text-gray-500 dark:text-gray-400">상태</th>
                    <th className="pb-2 text-left font-medium text-gray-500 dark:text-gray-400">엔드포인트</th>
                    <th className="pb-2 text-right font-medium text-gray-500 dark:text-gray-400">응답시간</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_errors.map((err, i) => (
                    <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
                      <td className="whitespace-nowrap py-2 text-gray-500 dark:text-gray-400">
                        {formatTime(err.created_at)}
                      </td>
                      <td className="py-2">
                        <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-bold ${statusBadgeBg(err.status_code)} ${statusColor(err.status_code)}`}>
                          {err.status_code}
                        </span>
                      </td>
                      <td className="py-2">
                        <span className="mr-1.5 inline-block rounded bg-gray-100 px-1.5 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                          {err.method}
                        </span>
                        <span className="text-gray-700 dark:text-gray-300">{err.path}</span>
                      </td>
                      <td className="py-2 text-right text-gray-500 dark:text-gray-400">
                        {formatDuration(err.duration_ms)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="py-12 text-center text-sm text-gray-400">에러 없음</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
