import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Newspaper, TrendingUp, BarChart3, Clock, Database, Zap, Loader2, Radio } from 'lucide-react'
import { cn, formatRelativeTime } from '@/lib/utils'
import { useTrackingStore } from '@/stores/useTrackingStore'
import { useTrendStore } from '@/stores/useTrendStore'
import { Card, CardContent } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import ThemeToggle from '@/components/ui/ThemeToggle'

export default function Header() {
  const location = useLocation()
  const navigate = useNavigate()
  const [panelOpen, setPanelOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  const { stats, crawlStatus, sseStatus, isLoading, loadStats, loadCrawlStatus, updateCrawlStatus, setSseStatus } = useTrendStore()

  // SSE with auto-reconnect (stats loaded on-demand when panel opens + SSE events)
  useEffect(() => {
    loadCrawlStatus()

    let es: EventSource | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let offlineTimer: ReturnType<typeof setTimeout> | null = null
    let retryDelay = 1000
    let unmounted = false
    let isFirstConnect = true

    function connect() {
      if (unmounted) return
      isFirstConnect = false
      es = new EventSource('/api/trends/events')

      es.onopen = () => {
        retryDelay = 1000
        if (offlineTimer) { clearTimeout(offlineTimer); offlineTimer = null }
        setSseStatus('connected')
      }

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'crawl_status') {
            updateCrawlStatus({ phase: data.phase, started_at: data.started_at, detail: data.detail })
            if (data.phase === 'idle') loadStats()
          }
          if (data.type === 'crawl_complete' || data.type === 'tracking_complete') {
            loadStats()
          }
        } catch {
          loadStats()
        }
      }

      es.onerror = () => {
        es?.close()
        es = null
        // 5초 이상 끊겨 있을 때만 'offline' 표시 (짧은 끊김은 무시)
        if (!offlineTimer && !isFirstConnect) {
          offlineTimer = setTimeout(() => { setSseStatus('offline') }, 5000)
        }
        if (!unmounted) {
          reconnectTimer = setTimeout(() => {
            retryDelay = Math.min(retryDelay * 2, 30000)
            connect()
          }, retryDelay)
        }
      }
    }

    connect()

    return () => {
      unmounted = true
      es?.close()
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (offlineTimer) clearTimeout(offlineTimer)
    }
  }, [loadStats, loadCrawlStatus, updateCrawlStatus])

  // Refresh stats when panel opens
  useEffect(() => {
    if (panelOpen) loadStats()
  }, [panelOpen, loadStats])

  // Close panel on outside click
  useEffect(() => {
    if (!panelOpen) return
    const handler = (e: MouseEvent) => {
      if (
        panelRef.current && !panelRef.current.contains(e.target as Node) &&
        buttonRef.current && !buttonRef.current.contains(e.target as Node)
      ) {
        setPanelOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [panelOpen])

  const navItems = [
    { to: '/', label: '추적', icon: Newspaper },
    { to: '/trends', label: '트렌드', icon: TrendingUp },
  ]

  const handleLogoClick = (e: React.MouseEvent) => {
    e.preventDefault()
    useTrackingStore.getState().reset()
    loadStats()
    loadCrawlStatus()
    useTrendStore.getState().loadArticleTrends()
    useTrendStore.getState().loadRecentArticles()
    navigate('/')
  }

  const handleHomeClick = () => {
    useTrackingStore.getState().reset()
  }

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-white/80 backdrop-blur-sm dark:bg-gray-950/80" role="banner">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-2 sm:px-4">
        <a href="/" onClick={handleLogoClick} className="flex shrink-0 items-center gap-1 text-sm font-bold whitespace-nowrap sm:gap-2 sm:text-lg" aria-label="News Origin 홈으로 이동">
          <Newspaper className="h-4 w-4 text-lifecycle-origin sm:h-5 sm:w-5" aria-hidden="true" />
          <span>
            News <span className="text-lifecycle-origin">Origin</span>
          </span>
        </a>

        <div className="relative flex min-w-0 flex-nowrap items-center gap-0 whitespace-nowrap sm:gap-1">
          <nav className="flex items-center gap-0 sm:gap-1" aria-label="주요 내비게이션">
            {navItems.map(({ to, label, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                onClick={to === '/' ? handleHomeClick : undefined}
                className={cn(
                  'flex items-center gap-0.5 rounded-md px-1.5 py-1 text-xs transition-colors sm:gap-1.5 sm:px-3 sm:py-1.5 sm:text-sm',
                  location.pathname === to
                    ? 'bg-secondary text-foreground'
                    : 'text-muted-foreground hover:text-foreground',
                )}
                aria-current={location.pathname === to ? 'page' : undefined}
              >
                <Icon className="h-3.5 w-3.5 sm:h-4 sm:w-4" aria-hidden="true" />
                {label}
              </Link>
            ))}
          </nav>

          <div className="ml-0.5 hidden h-5 w-px bg-border sm:ml-1 sm:block" />

          <ThemeToggle />

          <button
            ref={buttonRef}
            onClick={() => setPanelOpen((v) => !v)}
            className={cn(
              'flex items-center gap-0.5 rounded-md px-1 py-1 text-xs transition-colors sm:gap-1.5 sm:px-2.5 sm:py-1.5 sm:text-sm',
              panelOpen
                ? 'bg-secondary text-foreground'
                : 'text-muted-foreground hover:text-foreground',
            )}
            aria-label="수집 현황"
            aria-expanded={panelOpen}
          >
            {crawlStatus.phase !== 'idle' ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin sm:h-4 sm:w-4" aria-hidden="true" />
            ) : (
              <BarChart3 className="h-3.5 w-3.5 sm:h-4 sm:w-4" aria-hidden="true" />
            )}
            <span className="hidden sm:inline">현황</span>
            <span className="flex items-center gap-1" aria-label={`SSE 상태: ${SSE_STATUS_LABELS[sseStatus]?.label || '연결됨'}`}>
              <span className={`h-1.5 w-1.5 rounded-full sm:h-2 sm:w-2 ${SSE_STATUS_LABELS[sseStatus]?.dotClass || 'bg-emerald-400'}`} />
              {sseStatus !== 'connected' && (
                <span className="hidden text-xs text-muted-foreground sm:inline">{SSE_STATUS_LABELS[sseStatus]?.label}</span>
              )}
            </span>
          </button>

          {/* Floating stats panel */}
          <div
            ref={panelRef}
            className={cn(
              'absolute right-0 top-full mt-2 w-[min(calc(100vw-2rem),18rem)] origin-top-right transition-all duration-200',
              panelOpen
                ? 'pointer-events-auto scale-100 opacity-100'
                : 'pointer-events-none scale-95 opacity-0',
            )}
          >
            <div className="space-y-2 rounded-lg border border-border bg-white/95 p-2 shadow-xl backdrop-blur-md dark:bg-gray-950/95">
              {stats ? (
                <>
                  <Card className="border-0 bg-transparent shadow-none">
                    <CardContent className="px-3 py-2">
                      <div className="space-y-2">
                        <CrawlStatusRow phase={crawlStatus.phase} detail={crawlStatus.detail} />
                        <div className="border-t border-border/50" />
                        <StatRow icon={<BarChart3 className="h-3.5 w-3.5 text-lifecycle-spread" />} label="총 추적" value={stats.total_trackings} />
                        <StatRow icon={<Newspaper className="h-3.5 w-3.5 text-lifecycle-origin" />} label="수집된 기사" value={stats.total_articles} />
                        <StatRow icon={<TrendingUp className="h-3.5 w-3.5 text-lifecycle-explosion" />} label="진행 중" value={stats.active_trackings} />
                        <div className="border-t border-border/50" />
                        <StatRow icon={<Database className="h-3.5 w-3.5 text-lifecycle-sustained" />} label="임베딩 완료" value={stats.embedded_articles} />
                        <StatRow icon={<Zap className="h-3.5 w-3.5 text-lifecycle-resurge" />} label="최근 24h 수집" value={stats.recent_articles_24h} />
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                            <span className="text-[13px] text-muted-foreground">마지막 크롤링</span>
                          </div>
                          <span className="text-[13px] font-medium tabular-nums">
                            {stats.last_crawl_at ? formatRelativeTime(stats.last_crawl_at) : '-'}
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </>
              ) : isLoading ? (
                <Card className="border-0 bg-transparent shadow-none">
                  <CardContent className="space-y-2 px-3 py-2">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <div key={i} className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Skeleton className="h-3.5 w-3.5 rounded" />
                          <Skeleton className="h-3 w-16" />
                        </div>
                        <Skeleton className="h-3 w-10" />
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}

const CRAWL_PHASE_LABELS: Record<string, { label: string; dotClass: string }> = {
  idle: { label: '대기중', dotClass: 'bg-emerald-400' },
  fetching: { label: 'RSS 수집중', dotClass: 'bg-yellow-400 animate-pulse' },
  crawling: { label: '크롤링중', dotClass: 'bg-orange-400 animate-pulse' },
  embedding: { label: '임베딩 생성중', dotClass: 'bg-violet-400 animate-pulse' },
}

const SSE_STATUS_LABELS: Record<string, { label: string; dotClass: string }> = {
  connected: { label: '연결됨', dotClass: 'bg-emerald-400' },
  reconnecting: { label: '재연결 중...', dotClass: 'bg-yellow-400 animate-pulse' },
  offline: { label: '연결 끊김', dotClass: 'bg-red-400' },
}

function CrawlStatusRow({ phase, detail }: { phase: string; detail: string | null }) {
  const config = CRAWL_PHASE_LABELS[phase] || CRAWL_PHASE_LABELS.idle
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <Radio className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-[13px] text-muted-foreground">크롤링</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className={`h-2 w-2 rounded-full ${config.dotClass}`} />
        <span className="text-[13px] font-medium">{detail || config.label}</span>
      </div>
    </div>
  )
}

function StatRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: number
}) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-[13px] text-muted-foreground">{label}</span>
      </div>
      <span className="text-[13px] font-medium tabular-nums">{value.toLocaleString()}</span>
    </div>
  )
}

