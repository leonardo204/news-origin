import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Newspaper, TrendingUp, BarChart3, Clock, Database, Zap } from 'lucide-react'
import { cn, formatRelativeTime } from '@/lib/utils'
import { useTrackingStore } from '@/stores/useTrackingStore'
import { useTrendStore } from '@/stores/useTrendStore'
import { Card, CardContent } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'

const CATEGORY_LABELS: Record<string, string> = {
  headlines: '헤드라인',
  politics: '정치',
  economy: '경제',
  society: '사회',
  tech: 'IT/과학',
  entertainment: '연예/문화',
}

const CATEGORY_COLORS: Record<string, string> = {
  headlines: 'bg-emerald-400',
  politics: 'bg-blue-400',
  economy: 'bg-amber-400',
  society: 'bg-rose-400',
  tech: 'bg-violet-400',
  entertainment: 'bg-cyan-400',
}

export default function Header() {
  const location = useLocation()
  const navigate = useNavigate()
  const [panelOpen, setPanelOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  const { stats, isLoading, loadStats } = useTrendStore()

  // Load stats on mount + SSE
  useEffect(() => {
    loadStats()
    const es = new EventSource('/api/trends/events')
    es.onmessage = () => loadStats()
    es.onerror = () => {}
    return () => es.close()
  }, [loadStats])

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
    if (location.pathname === '/') {
      window.location.reload()
    } else {
      navigate('/')
    }
  }

  const handleHomeClick = () => {
    useTrackingStore.getState().reset()
  }

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-gray-950/80 backdrop-blur-sm" role="banner">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
        <a href="/" onClick={handleLogoClick} className="flex items-center gap-2 text-lg font-bold" aria-label="News Origin 홈으로 이동">
          <Newspaper className="h-5 w-5 text-lifecycle-origin" aria-hidden="true" />
          <span>
            News <span className="text-lifecycle-origin">Origin</span>
          </span>
        </a>

        <div className="relative flex items-center gap-1">
          <nav className="flex items-center gap-1" aria-label="주요 내비게이션">
            {navItems.map(({ to, label, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                onClick={to === '/' ? handleHomeClick : undefined}
                className={cn(
                  'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors',
                  location.pathname === to
                    ? 'bg-secondary text-foreground'
                    : 'text-muted-foreground hover:text-foreground',
                )}
                aria-current={location.pathname === to ? 'page' : undefined}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {label}
              </Link>
            ))}
          </nav>

          <div className="ml-1 h-5 w-px bg-border" />

          <button
            ref={buttonRef}
            onClick={() => setPanelOpen((v) => !v)}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm transition-colors',
              panelOpen
                ? 'bg-secondary text-foreground'
                : 'text-muted-foreground hover:text-foreground',
            )}
            aria-label="수집 현황"
            aria-expanded={panelOpen}
          >
            <BarChart3 className="h-4 w-4" aria-hidden="true" />
            <span className="hidden sm:inline">현황</span>
          </button>

          {/* Floating stats panel */}
          <div
            ref={panelRef}
            className={cn(
              'absolute right-0 top-full mt-2 w-56 origin-top-right transition-all duration-200',
              panelOpen
                ? 'pointer-events-auto scale-100 opacity-100'
                : 'pointer-events-none scale-95 opacity-0',
            )}
          >
            <div className="space-y-2 rounded-lg border border-border bg-gray-950/95 p-2 shadow-xl backdrop-blur-md">
              {stats ? (
                <>
                  <Card className="border-0 bg-transparent shadow-none">
                    <CardContent className="px-3 py-2">
                      <div className="space-y-2">
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
                  {Object.keys(stats.category_counts).length > 0 && (
                    <CategoryDistribution counts={stats.category_counts} />
                  )}
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

function CategoryDistribution({ counts }: { counts: Record<string, number> }) {
  const sorted = Object.entries(counts).sort(([, a], [, b]) => b - a)
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0)
  const maxCount = Math.max(...Object.values(counts))

  return (
    <Card className="border-0 bg-transparent shadow-none">
      <CardContent className="px-3 py-2">
        <div className="mb-3 flex items-baseline justify-between">
          <h3 className="text-[13px] font-medium text-muted-foreground">카테고리별 수집</h3>
          <span className="text-[11px] tabular-nums text-muted-foreground/60">
            {total.toLocaleString()}건
          </span>
        </div>
        <div className="space-y-2.5">
          {sorted.map(([category, count]) => {
            const pct = total > 0 ? Math.round((count / total) * 100) : 0
            return (
              <div key={category} className="space-y-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 shrink-0 rounded-full ${CATEGORY_COLORS[category] || 'bg-muted-foreground'}`} />
                    <span className="text-[12px] text-foreground/80">
                      {CATEGORY_LABELS[category] || category}
                    </span>
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-[12px] font-medium tabular-nums">{count.toLocaleString()}</span>
                    <span className="w-7 text-right text-[10px] tabular-nums text-muted-foreground/50">{pct}%</span>
                  </div>
                </div>
                <div className="h-1 overflow-hidden rounded-sm bg-muted/40">
                  <div
                    className={`h-full rounded-sm ${CATEGORY_COLORS[category] || 'bg-primary'}`}
                    style={{ width: `${(count / maxCount) * 100}%`, opacity: 0.65 }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
