import { useState, useEffect, useCallback, useRef } from 'react'
import {
  FileText,
  RefreshCw,
  Filter,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { fetchLogs } from '@/services/adminApi'

interface LogEntry {
  timestamp: string
  level: string
  logger: string
  message: string
}

interface LogsResponse {
  logs: LogEntry[]
  total: number
}

const LEVELS = ['ALL', 'DEBUG', 'INFO', 'WARNING', 'ERROR'] as const

function getLevelBadgeClass(level: string): string {
  switch (level.toUpperCase()) {
    case 'DEBUG':
      return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
    case 'INFO':
      return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
    case 'WARNING':
      return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
    case 'ERROR':
      return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
    default:
      return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
  }
}

function LoadingSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 12 }).map((_, i) => (
        <div
          key={i}
          className="h-7 animate-pulse rounded bg-gray-200 dark:bg-gray-800"
          style={{ width: `${70 + Math.random() * 30}%` }}
        />
      ))}
    </div>
  )
}

export default function LogsPage() {
  const [data, setData] = useState<LogsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [level, setLevel] = useState<string>('ALL')
  const [limit, setLimit] = useState(200)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadData = useCallback(async () => {
    try {
      const params: { level?: string; limit: number } = { limit }
      if (level !== 'ALL') params.level = level.toLowerCase()
      const { data: res } = await fetchLogs(params)
      setData(res)
      setError(null)
    } catch (err) {
      console.error('Logs fetch error:', err)
      setError('로그를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }, [level, limit])

  // Initial load and reload on filter change
  useEffect(() => {
    setLoading(true)
    loadData()
  }, [loadData])

  // Auto-refresh timer
  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    if (autoRefresh) {
      intervalRef.current = setInterval(loadData, 10000)
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [autoRefresh, loadData])

  const logs = data?.logs ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          시스템 로그
        </h2>
        {data && (
          <span className="text-xs text-gray-400 dark:text-gray-500">
            총 {data.total.toLocaleString('ko-KR')}건
          </span>
        )}
      </div>

      {/* Filters Row */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-4">
            {/* Level Filter Buttons */}
            <div className="flex items-center gap-1">
              <Filter className="mr-1 h-4 w-4 text-gray-400" />
              {LEVELS.map((l) => (
                <button
                  key={l}
                  onClick={() => setLevel(l)}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                    level === l
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700'
                  }`}
                >
                  {l}
                </button>
              ))}
            </div>

            <div className="h-5 w-px bg-gray-200 dark:bg-gray-700" />

            {/* Auto-refresh Toggle */}
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400"
            >
              {autoRefresh ? (
                <ToggleRight className="h-5 w-5 text-blue-500" />
              ) : (
                <ToggleLeft className="h-5 w-5 text-gray-400" />
              )}
              <span>자동 새로고침</span>
              {autoRefresh && (
                <span className="text-xs text-gray-400">(10초)</span>
              )}
            </button>

            <div className="h-5 w-px bg-gray-200 dark:bg-gray-700" />

            {/* Limit Selector */}
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-gray-500 dark:text-gray-400">
                표시:
              </span>
              {[100, 200, 500].map((n) => (
                <button
                  key={n}
                  onClick={() => setLimit(n)}
                  className={`rounded-md px-2 py-1 text-xs font-medium transition-colors ${
                    limit === n
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700'
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>

            {/* Manual Refresh */}
            <button
              onClick={() => {
                setLoading(true)
                loadData()
              }}
              disabled={loading}
              className="ml-auto flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`}
              />
              새로고침
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Log Viewer */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-gray-500" />
            로그 뷰어
            {autoRefresh && (
              <span className="ml-2 inline-flex h-2 w-2 rounded-full bg-emerald-500">
                <span className="inline-flex h-2 w-2 animate-ping rounded-full bg-emerald-400" />
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {error && !data ? (
            <div className="py-12 text-center">
              <p className="text-gray-500 dark:text-gray-400">{error}</p>
              <button
                onClick={() => {
                  setLoading(true)
                  loadData()
                }}
                className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
              >
                <RefreshCw className="h-4 w-4" />
                다시 시도
              </button>
            </div>
          ) : loading && !data ? (
            <LoadingSkeleton />
          ) : logs.length > 0 ? (
            <div className="max-h-[600px] overflow-auto rounded-lg border border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900/50">
              <table className="w-full text-left">
                <thead className="sticky top-0 border-b border-gray-200 bg-gray-100 dark:border-gray-700 dark:bg-gray-800">
                  <tr>
                    <th className="whitespace-nowrap px-3 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">
                      시간
                    </th>
                    <th className="whitespace-nowrap px-3 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">
                      레벨
                    </th>
                    <th className="whitespace-nowrap px-3 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">
                      로거
                    </th>
                    <th className="px-3 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">
                      메시지
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 font-mono text-sm dark:divide-gray-800">
                  {logs.map((log, idx) => (
                    <tr
                      key={idx}
                      className="hover:bg-gray-100/70 dark:hover:bg-gray-800/50"
                    >
                      <td className="whitespace-nowrap px-3 py-1.5 text-xs text-gray-400 dark:text-gray-500">
                        {log.timestamp}
                      </td>
                      <td className="px-3 py-1.5">
                        <span
                          className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase leading-tight ${getLevelBadgeClass(log.level)}`}
                        >
                          {log.level}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-1.5 text-xs text-gray-400 dark:text-gray-500">
                        {log.logger}
                      </td>
                      <td className="px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300">
                        {log.message}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="py-12 text-center text-sm text-gray-400 dark:text-gray-500">
              표시할 로그가 없습니다
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
