import { useState, useEffect } from 'react'
import {
  Newspaper,
  CalendarPlus,
  TrendingUp,
  Database,
  Activity,
  Clock,
  RefreshCw,
  Zap,
  Globe,
  Brain,
  FlaskConical,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { fetchOverview } from '@/services/adminApi'

interface OverviewData {
  articles: {
    total: number
    today: number
    this_week: number
    embedded_rate: number
  }
  crawl: {
    status: string
    last_run: string | null
    next_run: string | null
    articles_per_hour: number
  }
  system: {
    cpu_percent: number
    memory_percent: number
    disk_percent: number
  }
  services: {
    database: string
    redis: string
    qdrant: string
    celery: string
  }
  traffic?: {
    today: number
    error_rate: number
    avg_duration: number
    unique_ips: number
  }
  mlops?: {
    model_version: string
    model_f1: number | null
    training_total: number
    training_unused: number
    target_samples: number
    readiness_pct: number
    avg_quality: number
  }
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
      <div className="h-36 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
      <div className="h-28 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
      <div className="h-32 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
    </div>
  )
}

function getResourceColor(percent: number): string {
  if (percent > 80) return 'bg-red-500'
  if (percent > 60) return 'bg-yellow-500'
  return 'bg-emerald-500'
}

function getResourceTextColor(percent: number): string {
  if (percent > 80) return 'text-red-500'
  if (percent > 60) return 'text-yellow-500'
  return 'text-emerald-500'
}

function getServiceDot(status: string): string {
  switch (status) {
    case 'ok':
    case 'healthy':
      return 'bg-emerald-500 shadow-emerald-500/50'
    case 'degraded':
    case 'warning':
      return 'bg-yellow-500 shadow-yellow-500/50'
    default:
      return 'bg-red-500 shadow-red-500/50'
  }
}

function getServiceLabel(status: string): string {
  switch (status) {
    case 'ok':
    case 'healthy':
      return '정상'
    case 'degraded':
    case 'warning':
      return '저하'
    default:
      return '오류'
  }
}

function getCrawlStatusBadge(status: string) {
  switch (status) {
    case 'running':
      return {
        bg: 'bg-blue-100 dark:bg-blue-900/30',
        text: 'text-blue-700 dark:text-blue-400',
        label: '실행 중',
      }
    case 'idle':
      return {
        bg: 'bg-emerald-100 dark:bg-emerald-900/30',
        text: 'text-emerald-700 dark:text-emerald-400',
        label: '대기',
      }
    case 'error':
      return {
        bg: 'bg-red-100 dark:bg-red-900/30',
        text: 'text-red-700 dark:text-red-400',
        label: '오류',
      }
    default:
      return {
        bg: 'bg-gray-100 dark:bg-gray-800',
        text: 'text-gray-700 dark:text-gray-400',
        label: status,
      }
  }
}

const SERVICE_NAMES: Record<string, string> = {
  database: 'PostgreSQL',
  redis: 'Redis',
  qdrant: 'Qdrant',
  celery: 'Celery Worker',
}

export default function OverviewPage() {
  const [data, setData] = useState<OverviewData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const { data: res } = await fetchOverview()
      setData(res)
      setError(null)
    } catch (err) {
      console.error('Overview fetch error:', err)
      setError('데이터를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          대시보드 개요
        </h2>
        <LoadingSkeleton />
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          대시보드 개요
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
      value: data.articles.total.toLocaleString('ko-KR'),
      icon: Newspaper,
      iconColor: 'text-blue-500',
      iconBg: 'bg-blue-50 dark:bg-blue-900/20',
    },
    {
      label: '오늘 수집',
      value: data.articles.today.toLocaleString('ko-KR'),
      suffix: '건',
      icon: CalendarPlus,
      iconColor: 'text-emerald-500',
      iconBg: 'bg-emerald-50 dark:bg-emerald-900/20',
    },
    {
      label: '이번 주',
      value: data.articles.this_week.toLocaleString('ko-KR'),
      suffix: '건',
      icon: TrendingUp,
      iconColor: 'text-purple-500',
      iconBg: 'bg-purple-50 dark:bg-purple-900/20',
    },
    {
      label: '임베딩률',
      value: `${data.articles.embedded_rate.toFixed(1)}%`,
      icon: Database,
      iconColor: 'text-amber-500',
      iconBg: 'bg-amber-50 dark:bg-amber-900/20',
    },
  ]

  const resources = [
    { label: 'CPU', percent: data.system.cpu_percent },
    { label: '메모리', percent: data.system.memory_percent },
    { label: '디스크', percent: data.system.disk_percent },
  ]

  const crawlBadge = getCrawlStatusBadge(data.crawl.status)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          대시보드 개요
        </h2>
        <button
          onClick={loadData}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          새로고침
        </button>
      </div>

      {/* Row 1: Stat Cards */}
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
                    {card.suffix && (
                      <span className="ml-1 text-base font-normal text-gray-400">
                        {card.suffix}
                      </span>
                    )}
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

      {/* Row 2: Traffic Summary */}
      {data.traffic && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-5 w-5 text-blue-500" />
              트래픽 요약
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <div className="rounded-lg border border-gray-100 p-3 dark:border-gray-800">
                <p className="text-sm text-gray-500 dark:text-gray-400">오늘 요청</p>
                <p className="mt-1 text-xl font-bold text-gray-900 dark:text-gray-100">
                  {data.traffic.today.toLocaleString('ko-KR')}
                  <span className="ml-1 text-sm font-normal text-gray-400">건</span>
                </p>
              </div>
              <div className="rounded-lg border border-gray-100 p-3 dark:border-gray-800">
                <p className="text-sm text-gray-500 dark:text-gray-400">에러율 (30일)</p>
                <p className={`mt-1 text-xl font-bold ${data.traffic.error_rate > 5 ? 'text-red-500' : data.traffic.error_rate > 2 ? 'text-yellow-500' : 'text-emerald-500'}`}>
                  {data.traffic.error_rate.toFixed(1)}%
                </p>
              </div>
              <div className="rounded-lg border border-gray-100 p-3 dark:border-gray-800">
                <p className="text-sm text-gray-500 dark:text-gray-400">평균 응답 (30일)</p>
                <p className="mt-1 text-xl font-bold text-gray-900 dark:text-gray-100">
                  {data.traffic.avg_duration.toFixed(0)}
                  <span className="ml-1 text-sm font-normal text-gray-400">ms</span>
                </p>
              </div>
              <div className="rounded-lg border border-gray-100 p-3 dark:border-gray-800">
                <p className="text-sm text-gray-500 dark:text-gray-400">고유 방문자 (30일)</p>
                <p className="mt-1 text-xl font-bold text-gray-900 dark:text-gray-100">
                  {data.traffic.unique_ips.toLocaleString('ko-KR')}
                  <span className="ml-1 text-sm font-normal text-gray-400">IP</span>
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Row 3: MLOps Summary */}
      {data.mlops && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5 text-blue-500" />
              MLOps 요약
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <div className="rounded-lg border border-gray-100 p-3 dark:border-gray-800">
                  <p className="text-sm text-gray-500 dark:text-gray-400">현재 모델</p>
                  <p className="mt-1 text-sm font-bold text-gray-900 dark:text-gray-100">
                    {data.mlops.model_version}
                  </p>
                </div>
                <div className="rounded-lg border border-gray-100 p-3 dark:border-gray-800">
                  <p className="text-sm text-gray-500 dark:text-gray-400">모델 F1</p>
                  <p className="mt-1 text-xl font-bold text-gray-900 dark:text-gray-100">
                    {data.mlops.model_f1 != null ? `${(data.mlops.model_f1 * 100).toFixed(1)}%` : '-'}
                  </p>
                </div>
                <div className="rounded-lg border border-gray-100 p-3 dark:border-gray-800">
                  <p className="text-sm text-gray-500 dark:text-gray-400">평균 품질</p>
                  <p className={`mt-1 text-xl font-bold ${data.mlops.avg_quality >= 80 ? 'text-emerald-500' : data.mlops.avg_quality >= 60 ? 'text-yellow-500' : 'text-red-500'}`}>
                    {data.mlops.avg_quality.toFixed(1)}
                    <span className="ml-1 text-sm font-normal text-gray-400">점</span>
                  </p>
                </div>
                <div className="rounded-lg border border-gray-100 p-3 dark:border-gray-800">
                  <p className="text-sm text-gray-500 dark:text-gray-400">학습 데이터</p>
                  <p className="mt-1 text-xl font-bold text-gray-900 dark:text-gray-100">
                    {data.mlops.training_unused.toLocaleString('ko-KR')}
                    <span className="ml-1 text-sm font-normal text-gray-400">
                      / {data.mlops.target_samples.toLocaleString('ko-KR')}
                    </span>
                  </p>
                </div>
              </div>
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    학습 준비도
                  </span>
                  <span className={`text-sm font-semibold ${data.mlops.readiness_pct >= 100 ? 'text-emerald-500' : data.mlops.readiness_pct >= 60 ? 'text-yellow-500' : 'text-gray-500'}`}>
                    {data.mlops.readiness_pct}%
                  </span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${data.mlops.readiness_pct >= 100 ? 'bg-emerald-500' : data.mlops.readiness_pct >= 60 ? 'bg-yellow-500' : 'bg-blue-500'}`}
                    style={{ width: `${Math.min(data.mlops.readiness_pct, 100)}%` }}
                  />
                </div>
                {data.mlops.readiness_pct >= 100 && (
                  <div className="mt-2 flex items-center gap-1.5">
                    <FlaskConical className="h-3.5 w-3.5 text-emerald-500" />
                    <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
                      Fine-tuning 실행 가능
                    </span>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Row 4: Crawl Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-blue-500" />
            크롤링 상태
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">상태</p>
              <div className="mt-1">
                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${crawlBadge.bg} ${crawlBadge.text}`}
                >
                  {crawlBadge.label}
                </span>
              </div>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                마지막 실행
              </p>
              <p className="mt-1 text-sm font-medium text-gray-900 dark:text-gray-100">
                {data.crawl.last_run
                  ? new Date(data.crawl.last_run).toLocaleString('ko-KR')
                  : '-'}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                다음 실행
              </p>
              <p className="mt-1 text-sm font-medium text-gray-900 dark:text-gray-100">
                {data.crawl.next_run
                  ? new Date(data.crawl.next_run).toLocaleString('ko-KR')
                  : '-'}
              </p>
            </div>
          </div>
          <div className="mt-4 border-t border-gray-100 pt-4 dark:border-gray-800">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-gray-400" />
              <span className="text-sm text-gray-500 dark:text-gray-400">
                시간당 수집:
              </span>
              <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                {data.crawl.articles_per_hour.toLocaleString('ko-KR')}건
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Row 5: Service Health */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-blue-500" />
            서비스 상태
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(data.services).map(([key, status]) => (
              <div
                key={key}
                className="flex items-center gap-3 rounded-lg border border-gray-100 p-3 dark:border-gray-800"
              >
                <div
                  className={`h-3 w-3 rounded-full shadow-lg ${getServiceDot(status)}`}
                />
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                    {SERVICE_NAMES[key] || key}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {getServiceLabel(status)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Row 6: System Resources */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-blue-500" />
            시스템 리소스
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {resources.map((res) => (
              <div key={res.label}>
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {res.label}
                  </span>
                  <span
                    className={`text-sm font-semibold ${getResourceTextColor(res.percent)}`}
                  >
                    {res.percent.toFixed(1)}%
                  </span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${getResourceColor(res.percent)}`}
                    style={{ width: `${Math.min(res.percent, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
