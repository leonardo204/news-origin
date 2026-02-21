import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, ExternalLink, Building2, Clock, Share2, Check, Download, Network, X, Radio, Loader2, Zap, FileQuestion } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import EmptyState from '@/components/ui/EmptyState'
import BookmarkButton from '@/components/ui/BookmarkButton'
import ViewToggle from '@/components/visualization/ViewToggle'
import LifecyclePanel from '@/components/visualization/LifecyclePanel'
import ArticleDetailPanel from '@/components/visualization/ArticleDetailPanel'
import { useTrackingStore } from '@/stores/useTrackingStore'
import { usePageTitle } from '@/hooks/usePageTitle'
import { formatDate } from '@/lib/utils'
import type { GraphNode, TimelineItem } from '@/types'

// Lazy load heavy visualization components
const PropagationGraph = lazy(() => import('@/components/visualization/PropagationGraph'))
const DensityChart = lazy(() => import('@/components/visualization/DensityChart'))

// TimelineChart is a lightweight React component — no lazy load needed
import TimelineChart from '@/components/visualization/TimelineChart'

function ChartFallback() {
  return (
    <div className="h-96 p-4">
      <Skeleton className="h-full w-full rounded-lg" />
    </div>
  )
}

function downloadFile(content: string, filename: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function exportToCSV(items: TimelineItem[], originTitle: string) {
  const header = '제목,언론사,발행시간,유사도,단계\n'
  const rows = items
    .map((item) =>
      [
        `"${item.title.replace(/"/g, '""')}"`,
        `"${(item.publisher || '').replace(/"/g, '""')}"`,
        item.published_at,
        (item.similarity_score * 100).toFixed(1) + '%',
        item.lifecycle_stage,
      ].join(','),
    )
    .join('\n')
  const bom = '\uFEFF'
  const safeName = originTitle.slice(0, 20).replace(/[/\\?%*:|"<>]/g, '')
  downloadFile(bom + header + rows, `news-origin-${safeName}.csv`, 'text/csv;charset=utf-8')
}

function exportToJSON(items: TimelineItem[], originTitle: string) {
  const data = {
    origin_title: originTitle,
    exported_at: new Date().toISOString(),
    total_articles: items.length,
    articles: items,
  }
  const safeName = originTitle.slice(0, 20).replace(/[/\\?%*:|"<>]/g, '')
  downloadFile(JSON.stringify(data, null, 2), `news-origin-${safeName}.json`, 'application/json')
}

export default function TimelinePage() {
  const { trackingId } = useParams<{ trackingId: string }>()
  const {
    timeline,
    isLoadingTimeline,
    viewMode,
    loadTimeline,
    trackingStatus,
    isPolling,
    isLiveTracking,
    startLiveTrack,
  } = useTrackingStore()

  const navigate = useNavigate()
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [copied, setCopied] = useState(false)
  const [showExport, setShowExport] = useState(false)
  const [showGraph, setShowGraph] = useState(false)

  // Navigate to live tracking result when complete
  useEffect(() => {
    if (
      isLiveTracking &&
      trackingStatus?.status === 'completed' &&
      trackingStatus.tracking_type === 'live' &&
      trackingStatus.tracking_id !== trackingId
    ) {
      navigate(`/timeline/${trackingStatus.tracking_id}`, { replace: true })
    }
  }, [isLiveTracking, trackingStatus, trackingId, navigate])
  const exportRef = useRef<HTMLDivElement>(null)

  usePageTitle(timeline?.origin_article?.title)

  // Close export dropdown on outside click
  useEffect(() => {
    if (!showExport) return
    function handleClick(e: MouseEvent) {
      if (exportRef.current && !exportRef.current.contains(e.target as Node)) {
        setShowExport(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [showExport])

  // ESC to close graph overlay
  useEffect(() => {
    if (!showGraph) return
    function handleEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') setShowGraph(false)
    }
    document.addEventListener('keydown', handleEsc)
    return () => document.removeEventListener('keydown', handleEsc)
  }, [showGraph])

  // Lock body scroll when graph overlay is open
  useEffect(() => {
    if (showGraph) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [showGraph])

  const handleShare = useCallback(async () => {
    const url = window.location.href
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback for older browsers
      const input = document.createElement('input')
      input.value = url
      document.body.appendChild(input)
      input.select()
      document.execCommand('copy')
      document.body.removeChild(input)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }, [])

  useEffect(() => {
    if (!trackingId) return

    if (trackingStatus?.status === 'completed' && trackingStatus.tracking_id === trackingId) {
      if (!timeline || timeline.tracking_id !== trackingId) {
        loadTimeline(trackingId)
      }
    } else if (!timeline || timeline.tracking_id !== trackingId) {
      loadTimeline(trackingId)
    }
  }, [trackingId, trackingStatus, timeline, loadTimeline, isPolling])

  if (isLoadingTimeline) {
    return (
      <div className="mx-auto max-w-7xl overflow-x-hidden px-4 py-6">
        <div className="mb-6">
          <Skeleton className="mb-2 h-3 w-12" />
          <Skeleton className="mb-3 h-7 w-2/3" />
          <div className="flex gap-3">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-16" />
          </div>
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
          <div className="space-y-6">
            <Card>
              <CardContent className="p-2 sm:p-4">
                <Skeleton className="h-96 w-full" />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <Skeleton className="mb-4 h-5 w-32" />
                <div className="space-y-2">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
          <div className="hidden space-y-4 lg:block">
            <Card>
              <CardContent className="p-4">
                <Skeleton className="mb-3 h-5 w-24" />
                <div className="space-y-2">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-8 w-full" />
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    )
  }

  if (!timeline) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <EmptyState
          icon={<FileQuestion className="h-12 w-12" />}
          title="타임라인 데이터를 찾을 수 없습니다"
          description="요청하신 추적 기록이 존재하지 않거나 삭제되었습니다."
          action={{
            label: '새 검색 시작',
            onClick: () => {
              useTrackingStore.getState().reset()
              navigate('/')
            },
          }}
        />
      </div>
    )
  }

  const { origin_article, graph, lifecycle, explosions } = timeline

  return (
    <div className="mx-auto max-w-7xl overflow-x-hidden px-4 py-6">
      {/* Top bar */}
      <div className="mb-6 space-y-3">
        <div>
          <Link
            to="/"
            onClick={() => useTrackingStore.getState().reset()}
            className="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-3 w-3" />
            홈
          </Link>
          <h1 className="text-lg font-bold leading-tight sm:text-xl">{origin_article.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground sm:gap-3 sm:text-sm">
            {origin_article.publisher && (
              <span className="flex items-center gap-1">
                <Building2 className="h-3.5 w-3.5" />
                {origin_article.publisher}
              </span>
            )}
            {origin_article.published_at && (
              <span className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                {formatDate(origin_article.published_at)}
              </span>
            )}
            <a
              href={origin_article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-lifecycle-origin hover:underline"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              원문 보기
            </a>
            <Badge stage="origin">기원</Badge>
            <BookmarkButton
              articleId={origin_article.id}
              title={origin_article.title}
              publisher={origin_article.publisher || undefined}
              url={origin_article.url}
              size="sm"
            />
            {timeline.tracking_type === 'live' ? (
              <span className="flex items-center gap-1 rounded-full bg-lifecycle-origin/15 px-2 py-0.5 text-xs font-medium text-lifecycle-origin">
                <Radio className="h-3 w-3" />
                Live 데이터
              </span>
            ) : (
              <span className="flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                <Zap className="h-3 w-3" />
                즉시 분석
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Live tracking button - only show for instant results */}
          {timeline.tracking_type !== 'live' && !isLiveTracking && (
            <Button
              variant="default"
              size="sm"
              onClick={() => trackingId && startLiveTrack(trackingId)}
              className="gap-1.5 bg-lifecycle-origin hover:bg-lifecycle-origin/90"
            >
              <Radio className="h-3.5 w-3.5" />
              Live 추적
            </Button>
          )}
          {/* Live tracking in progress */}
          {isLiveTracking && isPolling && (
            <div className="flex items-center gap-2 rounded-md border border-lifecycle-origin/30 bg-lifecycle-origin/10 px-3 py-1.5">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-lifecycle-origin" />
              <span className="text-xs font-medium text-lifecycle-origin">
                Live 추적 중... {trackingStatus?.progress ?? 0}%
              </span>
            </div>
          )}
          {/* Propagation tree button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowGraph(true)}
            className="gap-1.5"
          >
            <Network className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">전파 트리</span>
          </Button>
          {/* Export dropdown */}
          <div className="relative" ref={exportRef}>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowExport(!showExport)}
              className="gap-1.5"
              aria-label="타임라인 데이터 내보내기"
              aria-expanded={showExport}
              aria-haspopup="menu"
            >
              <Download className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="hidden sm:inline">내보내기</span>
            </Button>
            {showExport && (
              <div className="absolute right-0 top-full z-20 mt-1 w-36 rounded-md border border-border bg-card p-1 shadow-lg" role="menu">
                <button
                  role="menuitem"
                  className="w-full rounded-sm px-3 py-1.5 text-left text-sm hover:bg-secondary/50"
                  onClick={() => {
                    exportToCSV(timeline.timeline, origin_article.title)
                    setShowExport(false)
                  }}
                >
                  CSV 다운로드
                </button>
                <button
                  role="menuitem"
                  className="w-full rounded-sm px-3 py-1.5 text-left text-sm hover:bg-secondary/50"
                  onClick={() => {
                    exportToJSON(timeline.timeline, origin_article.title)
                    setShowExport(false)
                  }}
                >
                  JSON 다운로드
                </button>
              </div>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleShare}
            className="gap-1.5"
            aria-label="링크 공유"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-green-400" />
                <span className="hidden sm:inline">복사됨</span>
              </>
            ) : (
              <>
                <Share2 className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">공유</span>
              </>
            )}
          </Button>
          <ViewToggle />
        </div>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        {/* Visualization */}
        <div className="space-y-6">
          <Card>
            <CardContent className="relative overflow-hidden p-2 sm:p-4">
              {viewMode === 'timeline' && (
                <TimelineChart items={timeline.timeline} explosions={explosions} />
              )}
              <Suspense fallback={<ChartFallback />}>
                {viewMode === 'density' && (
                  <DensityChart density={timeline.density} explosions={explosions} />
                )}
              </Suspense>
            </CardContent>
          </Card>

          {/* Sidebar - shown inline on mobile */}
          <div className="lg:hidden">
            <LifecyclePanel lifecycle={lifecycle} />
          </div>

        </div>

        {/* Sidebar - desktop only */}
        <div className="hidden space-y-4 lg:block">
          <LifecyclePanel lifecycle={lifecycle} />
        </div>
      </div>

      {/* Fullscreen graph overlay */}
      {showGraph && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          {/* Modal: full-screen on mobile, centered on desktop */}
          <div className="flex h-full w-full flex-col bg-background sm:h-[95vh] sm:w-[97vw] sm:rounded-2xl sm:border sm:border-border sm:shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border px-3 py-3 sm:px-5">
              <div className="flex items-center gap-2 sm:gap-3">
                <Network className="h-5 w-5 text-lifecycle-origin" />
                <h2 className="text-sm font-semibold sm:text-base">전파 트리</h2>
                <span className="text-xs text-muted-foreground">
                  {graph.nodes.length}개 노드 · {graph.edges.length}개 연결
                </span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowGraph(false)
                  setSelectedNode(null)
                }}
                className="gap-1.5"
              >
                <X className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">닫기</span>
                <kbd className="ml-1 hidden rounded border border-border px-1 py-0.5 text-[10px] text-muted-foreground sm:inline">ESC</kbd>
              </Button>
            </div>
            {/* Graph content */}
            <div className="relative flex-1 overflow-hidden">
              <Suspense fallback={<ChartFallback />}>
                <PropagationGraph
                  nodes={graph.nodes}
                  edges={graph.edges}
                  onNodeClick={(node) => setSelectedNode(node)}
                  className="h-full"
                />
                <ArticleDetailPanel
                  node={selectedNode}
                  onClose={() => setSelectedNode(null)}
                />
              </Suspense>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
