import { useState, useEffect } from 'react'
import {
  Server,
  Cpu,
  MemoryStick,
  HardDrive,
  RefreshCw,
  Clock,
  Monitor,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { fetchSystem } from '@/services/adminApi'

interface SystemData {
  hostname: string
  platform: string
  uptime_seconds: number
  cpu: {
    percent: number
    count: number
    freq_mhz: number
  }
  memory: {
    total_gb: number
    used_gb: number
    percent: number
    available_gb: number
  }
  disk: {
    total_gb: number
    used_gb: number
    percent: number
    free_gb: number
  }
  python_version: string
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-24 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="h-52 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800"
          />
        ))}
      </div>
    </div>
  )
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)

  const parts: string[] = []
  if (days > 0) parts.push(`${days}일`)
  if (hours > 0) parts.push(`${hours}시간`)
  parts.push(`${minutes}분`)
  return parts.join(' ')
}

function GaugeRing({
  percent,
  label,
  detail,
  icon: Icon,
}: {
  percent: number
  label: string
  detail: string
  icon: React.ComponentType<{ className?: string }>
}) {
  const color =
    percent > 80 ? '#EF4444' : percent > 60 ? '#F59E0B' : '#10B981'
  const circumference = 2 * Math.PI * 45
  const offset = circumference - (percent / 100) * circumference

  return (
    <div className="flex flex-col items-center py-4">
      <div className="relative">
        <svg width="140" height="140" className="-rotate-90">
          <circle
            cx="70"
            cy="70"
            r="45"
            fill="none"
            stroke="currentColor"
            strokeWidth="10"
            className="text-gray-200 dark:text-gray-700"
          />
          <circle
            cx="70"
            cy="70"
            r="45"
            fill="none"
            stroke={color}
            strokeWidth="10"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-all duration-700"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <Icon className="h-5 w-5 text-gray-400 dark:text-gray-500" />
          <span className="mt-1 text-2xl font-bold text-gray-900 dark:text-gray-100">
            {percent.toFixed(1)}%
          </span>
        </div>
      </div>
      <p className="mt-3 text-sm font-medium text-gray-700 dark:text-gray-300">
        {label}
      </p>
      <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">{detail}</p>
    </div>
  )
}

export default function SystemPage() {
  const [data, setData] = useState<SystemData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const { data: res } = await fetchSystem()
      setData(res)
      setError(null)
    } catch (err) {
      console.error('System fetch error:', err)
      setError('시스템 데이터를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          시스템 모니터링
        </h2>
        <LoadingSkeleton />
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          시스템 모니터링
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

  const infoItems = [
    { label: '호스트명', value: data.hostname },
    { label: '플랫폼', value: data.platform },
    { label: 'Python 버전', value: data.python_version },
    { label: '업타임', value: formatUptime(data.uptime_seconds) },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          시스템 모니터링
        </h2>
        <button
          onClick={loadData}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          새로고침
        </button>
      </div>

      {/* System Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Monitor className="h-5 w-5 text-blue-500" />
            시스템 정보
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {infoItems.map((item) => (
              <div
                key={item.label}
                className="rounded-lg border border-gray-100 p-3 dark:border-gray-800"
              >
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {item.label}
                </p>
                <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-100">
                  {item.value}
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Resource Gauges */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="h-5 w-5 text-blue-500" />
              CPU
            </CardTitle>
          </CardHeader>
          <CardContent>
            <GaugeRing
              percent={data.cpu.percent}
              label="CPU 사용률"
              detail={`${data.cpu.count}코어 / ${data.cpu.freq_mhz.toLocaleString('ko-KR')} MHz`}
              icon={Cpu}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MemoryStick className="h-5 w-5 text-purple-500" />
              메모리
            </CardTitle>
          </CardHeader>
          <CardContent>
            <GaugeRing
              percent={data.memory.percent}
              label="메모리 사용률"
              detail={`${data.memory.used_gb.toFixed(1)} / ${data.memory.total_gb.toFixed(1)} GB`}
              icon={MemoryStick}
            />
            <div className="mt-2 flex justify-center">
              <span className="text-xs text-gray-400 dark:text-gray-500">
                사용 가능: {data.memory.available_gb.toFixed(1)} GB
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <HardDrive className="h-5 w-5 text-amber-500" />
              디스크
            </CardTitle>
          </CardHeader>
          <CardContent>
            <GaugeRing
              percent={data.disk.percent}
              label="디스크 사용률"
              detail={`${data.disk.used_gb.toFixed(1)} / ${data.disk.total_gb.toFixed(1)} GB`}
              icon={HardDrive}
            />
            <div className="mt-2 flex justify-center">
              <span className="text-xs text-gray-400 dark:text-gray-500">
                여유 공간: {data.disk.free_gb.toFixed(1)} GB
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Resource Bars */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5 text-gray-500" />
            리소스 상세
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-5">
            {[
              {
                label: 'CPU',
                percent: data.cpu.percent,
                used: `${data.cpu.percent.toFixed(1)}%`,
                total: `${data.cpu.count}코어`,
              },
              {
                label: '메모리',
                percent: data.memory.percent,
                used: `${data.memory.used_gb.toFixed(1)} GB`,
                total: `${data.memory.total_gb.toFixed(1)} GB`,
              },
              {
                label: '디스크',
                percent: data.disk.percent,
                used: `${data.disk.used_gb.toFixed(1)} GB`,
                total: `${data.disk.total_gb.toFixed(1)} GB`,
              },
            ].map((res) => {
              const barColor =
                res.percent > 80
                  ? 'bg-red-500'
                  : res.percent > 60
                    ? 'bg-yellow-500'
                    : 'bg-emerald-500'
              const textColor =
                res.percent > 80
                  ? 'text-red-500'
                  : res.percent > 60
                    ? 'text-yellow-500'
                    : 'text-emerald-500'
              return (
                <div key={res.label}>
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      {res.label}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-gray-400">
                        {res.used} / {res.total}
                      </span>
                      <span className={`text-sm font-semibold ${textColor}`}>
                        {res.percent.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <div className="h-2.5 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                      style={{ width: `${Math.min(res.percent, 100)}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>

          {/* Uptime Footer */}
          <div className="mt-6 flex items-center gap-2 border-t border-gray-100 pt-4 dark:border-gray-800">
            <Clock className="h-4 w-4 text-gray-400" />
            <span className="text-sm text-gray-500 dark:text-gray-400">
              서버 업타임:
            </span>
            <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
              {formatUptime(data.uptime_seconds)}
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
