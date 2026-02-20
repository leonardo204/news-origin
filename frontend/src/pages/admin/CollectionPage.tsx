import { useState, useEffect } from 'react'
import {
  Rss,
  Clock,
  RefreshCw,
  Building2,
  Tag,
  Newspaper,
  Globe,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { fetchCrawl } from '@/services/adminApi'

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
      <div className="h-24 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="h-64 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
        <div className="h-64 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
      </div>
      <div className="h-80 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
    </div>
  )
}

export default function CollectionPage() {
  const [data, setData] = useState<CrawlData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const { data: res } = await fetchCrawl()
      setData(res)
      setError(null)
    } catch (err) {
      console.error('Crawl fetch error:', err)
      setError('수집 데이터를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          뉴스 수집 관리
        </h2>
        <LoadingSkeleton />
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          뉴스 수집 관리
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

  const maxCategoryCount = Math.max(...data.category_stats.map((c) => c.count), 1)
  const maxPublisherCount = Math.max(
    ...data.publisher_stats.map((p) => p.count),
    1
  )
  const maxDailyCount = Math.max(...data.daily_counts.map((d) => d.count), 1)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          뉴스 수집 관리
        </h2>
        <button
          onClick={loadData}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          새로고침
        </button>
      </div>

      {/* Schedule Info */}
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
                {data.schedule.interval_minutes}분
              </span>
            </div>
            <div className="h-4 w-px bg-gray-200 dark:bg-gray-700" />
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">
                카테고리:
              </span>
              {data.schedule.categories.map((cat) => (
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

      {/* Feed Sources */}
      {data.feed_sources && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Category Feeds */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Globe className="h-5 w-5 text-blue-500" />
                카테고리 피드
                <span className="ml-auto text-xs font-normal text-gray-400">
                  피드당 최대 {data.feed_sources.limits.per_category}건
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {data.feed_sources.categories.map((feed) => (
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
                  피드당 최대 {data.feed_sources.limits.per_publisher}건
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {data.feed_sources.publishers.map((pub) => (
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

      {/* Category + Publisher Stats */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Category Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Tag className="h-5 w-5 text-purple-500" />
              카테고리별 수집 현황
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {data.category_stats.map((cat) => (
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
              {data.category_stats.length === 0 && (
                <p className="py-4 text-center text-sm text-gray-400">
                  데이터 없음
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Top Publishers */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5 text-emerald-500" />
              주요 언론사
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2.5">
              {data.publisher_stats.slice(0, 10).map((pub, idx) => (
                <div key={pub.publisher} className="flex items-center gap-3">
                  <span className="w-5 text-right text-xs font-medium text-gray-400">
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
              {data.publisher_stats.length === 0 && (
                <p className="py-4 text-center text-sm text-gray-400">
                  데이터 없음
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Daily Collection Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Rss className="h-5 w-5 text-blue-500" />
            일별 수집량 (최근 14일)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.daily_counts.length > 0 ? (
            <div>
              <div className="flex items-end gap-1 h-32">
                {data.daily_counts.map((d) => (
                  <div
                    key={d.date}
                    className="group relative flex-1"
                    style={{ height: '100%' }}
                  >
                    <div
                      className="absolute bottom-0 left-0 right-0 rounded-t bg-blue-500 transition-all duration-300 hover:bg-blue-400"
                      style={{
                        height: `${Math.max((d.count / maxDailyCount) * 100, 2)}%`,
                      }}
                    />
                    <div className="absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-gray-900 px-2 py-1 text-xs text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 dark:bg-gray-700">
                      {d.date}: {d.count.toLocaleString('ko-KR')}건
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-2 flex justify-between">
                <span className="text-xs text-gray-400">
                  {data.daily_counts[0]?.date}
                </span>
                <span className="text-xs text-gray-400">
                  {data.daily_counts[data.daily_counts.length - 1]?.date}
                </span>
              </div>
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-gray-400">
              데이터 없음
            </p>
          )}
        </CardContent>
      </Card>

      {/* Recent Articles Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Newspaper className="h-5 w-5 text-amber-500" />
            최근 수집 기사
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.recent_articles.length > 0 ? (
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
                  {data.recent_articles.map((article, idx) => (
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
          ) : (
            <p className="py-8 text-center text-sm text-gray-400">
              최근 수집된 기사가 없습니다
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
