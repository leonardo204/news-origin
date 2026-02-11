import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  TrendingUp,
  Search,
  BarChart3,
  Clock,
  Newspaper,
  Flame,
} from 'lucide-react'
import ReactECharts from 'echarts-for-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { useTrendStore } from '@/stores/useTrendStore'
import { usePageTitle } from '@/hooks/usePageTitle'
import { formatRelativeTime, truncate } from '@/lib/utils'

export default function TrendsPage() {
  usePageTitle('트렌드')
  const navigate = useNavigate()
  const { trends, popularSearches, stats, isLoading, error, period, setPeriod, loadTrends, loadStats } =
    useTrendStore()

  useEffect(() => {
    loadTrends()
    loadStats()
  }, [loadTrends, loadStats])

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <TrendingUp className="h-6 w-6 text-lifecycle-explosion" />
          트렌드
        </h1>
        <div className="inline-flex items-center rounded-lg border border-border bg-secondary/50 p-1">
          {(['24h', '7d', '30d'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
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

      {/* Stats Overview */}
      {stats && (
        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card>
            <CardContent className="flex items-center gap-3 p-4">
              <BarChart3 className="h-8 w-8 text-lifecycle-spread" />
              <div>
                <p className="text-xs text-muted-foreground">총 추적</p>
                <p className="text-3xl font-bold tabular-nums">
                  {stats.total_trackings.toLocaleString()}
                </p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex items-center gap-3 p-4">
              <Newspaper className="h-8 w-8 text-lifecycle-origin" />
              <div>
                <p className="text-xs text-muted-foreground">수집된 기사</p>
                <p className="text-3xl font-bold tabular-nums">
                  {stats.total_articles.toLocaleString()}
                </p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex items-center gap-3 p-4">
              <Flame className="h-8 w-8 text-lifecycle-explosion" />
              <div>
                <p className="text-xs text-muted-foreground">진행 중</p>
                <p className="text-3xl font-bold tabular-nums">
                  {stats.active_trackings.toLocaleString()}
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <Skeleton className="h-5 w-32" />
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="flex items-center gap-3 p-3">
                      <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
                      <div className="flex-1 space-y-1">
                        <Skeleton className="h-4 w-3/4" />
                        <Skeleton className="h-3 w-1/3" />
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
                <div className="space-y-1">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <Skeleton key={i} className="h-8 w-full" />
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
          {/* Hot Trends */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Flame className="h-4 w-4 text-lifecycle-explosion" />
                  실시간 트렌드
                </CardTitle>
              </CardHeader>
              <CardContent>
                {trends.length === 0 ? (
                  <p className="py-8 text-center text-muted-foreground">
                    아직 추적 데이터가 없습니다.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {trends.map((trend, i) => (
                      <div
                        key={trend.latest_tracking_id || i}
                        className="flex cursor-pointer items-center gap-3 rounded-lg p-3 transition-colors hover:bg-secondary/50"
                        onClick={() => {
                          if (trend.latest_tracking_id) {
                            navigate(`/timeline/${trend.latest_tracking_id}`)
                          }
                        }}
                      >
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-lifecycle-explosion/10 text-sm font-bold text-lifecycle-explosion">
                          {i + 1}
                        </span>
                        <div className="flex-1">
                          <p className="text-sm font-medium leading-tight">
                            {truncate(trend.title, 80)}
                          </p>
                          <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                            <span className="flex items-center gap-1">
                              <BarChart3 className="h-3 w-3" />
                              {trend.tracking_count}회
                            </span>
                            {trend.last_tracked_at && (
                              <span className="flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                {formatRelativeTime(trend.last_tracked_at)}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Trend Chart */}
            {trends.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>추적 빈도</CardTitle>
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
                      },
                      grid: { left: 10, right: 10, top: 10, bottom: 30, containLabel: true },
                      xAxis: {
                        type: 'category',
                        data: trends.slice(0, 10).map((t) => truncate(t.title, 15)),
                        axisLabel: { color: '#9ca3af', fontSize: 10, rotate: 30 },
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
                          data: trends.slice(0, 10).map((t) => t.tracking_count),
                          itemStyle: {
                            color: {
                              type: 'linear',
                              x: 0, y: 0, x2: 0, y2: 1,
                              colorStops: [
                                { offset: 0, color: '#ef4444' },
                                { offset: 1, color: '#7f1d1d' },
                              ],
                            },
                            borderRadius: [4, 4, 0, 0],
                          },
                          barWidth: '60%',
                        },
                      ],
                    }}
                    style={{ height: 300 }}
                    theme="dark"
                  />
                </CardContent>
              </Card>
            )}
          </div>

          {/* Sidebar: Popular Searches */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Search className="h-4 w-4 text-lifecycle-spread" />
                  인기 검색어
                </CardTitle>
              </CardHeader>
              <CardContent>
                {popularSearches.length === 0 ? (
                  <p className="py-4 text-center text-sm text-muted-foreground">
                    검색 기록이 없습니다.
                  </p>
                ) : (
                  <div className="space-y-1">
                    {popularSearches.slice(0, 15).map((ps, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-secondary/30"
                      >
                        <span className="flex-1 truncate text-muted-foreground">
                          {ps.query}
                        </span>
                        <span className="ml-2 shrink-0 tabular-nums text-xs text-muted-foreground">
                          {ps.count}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <p className="mb-3 text-sm text-muted-foreground">
                  뉴스 기사의 기원을 추적해보세요
                </p>
                <Button
                  className="w-full"
                  onClick={() => navigate('/')}
                >
                  <Search className="mr-1.5 h-4 w-4" />
                  추적 시작하기
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}
