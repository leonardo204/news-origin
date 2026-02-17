import { useEffect, useRef, useCallback, useState, useMemo } from 'react'
import { ZoomIn, ZoomOut, Maximize2, Minimize2, Info } from 'lucide-react'
import { Graph } from '@antv/g6'
import { LIFECYCLE_COLORS, LIFECYCLE_LABELS, truncate } from '@/lib/utils'
import type { GraphNode, GraphEdge, LifecycleStage } from '@/types'

interface PropagationGraphProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  onNodeClick?: (node: GraphNode) => void
  className?: string
}

export default function PropagationGraph({ nodes, edges, onNodeClick, className }: PropagationGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<Graph | null>(null)
  const destroyedRef = useRef(false)
  const nodesRef = useRef(nodes)
  nodesRef.current = nodes
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showLegend, setShowLegend] = useState(false)
  const [showAllNodes, setShowAllNodes] = useState(false)

  // Limit nodes to top 50 by similarity_score when count exceeds 50
  const NODE_LIMIT = 50
  const hasExcessNodes = nodes.length > NODE_LIMIT
  const limitedNodes = useMemo(() => {
    if (!hasExcessNodes || showAllNodes) return nodes
    const origin = nodes.find(n => n.is_origin)
    const nonOrigin = nodes.filter(n => !n.is_origin)
      .sort((a, b) => (b.similarity_score || 0) - (a.similarity_score || 0))
      .slice(0, NODE_LIMIT - (origin ? 1 : 0))
    return origin ? [origin, ...nonOrigin] : nonOrigin
  }, [nodes, hasExcessNodes, showAllNodes])

  const limitedEdges = useMemo(() => {
    if (!hasExcessNodes || showAllNodes) return edges
    const nodeIds = new Set(limitedNodes.map(n => n.id))
    return edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
  }, [edges, limitedNodes, hasExcessNodes, showAllNodes])

  const handleNodeClick = useCallback(
    (nodeId: string) => {
      const node = nodesRef.current.find((n) => n.id === nodeId)
      if (node) {
        if (onNodeClick) {
          onNodeClick(node)
        } else {
          window.open(node.url || '#', '_blank', 'noopener,noreferrer')
        }
      }
    },
    [onNodeClick],
  )

  // ESC to exit fullscreen
  useEffect(() => {
    if (!isFullscreen) return
    function handleEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') setIsFullscreen(false)
    }
    document.addEventListener('keydown', handleEsc)
    return () => document.removeEventListener('keydown', handleEsc)
  }, [isFullscreen])

  const handleZoomIn = useCallback(() => {
    if (graphRef.current) graphRef.current.zoomTo(1.3)
  }, [])
  const handleZoomOut = useCallback(() => {
    if (graphRef.current) graphRef.current.zoomTo(0.7)
  }, [])
  const handleFitView = useCallback(() => {
    if (graphRef.current) graphRef.current.fitView()
  }, [])
  const toggleFullscreen = useCallback(() => {
    setIsFullscreen((prev) => !prev)
    setTimeout(() => {
      if (graphRef.current && containerRef.current) {
        graphRef.current.resize(
          containerRef.current.offsetWidth,
          containerRef.current.offsetHeight,
        )
        graphRef.current.fitView()
      }
    }, 100)
  }, [])

  // Detect dark mode
  const isDark = typeof document !== 'undefined' && document.documentElement.classList.contains('dark')

  useEffect(() => {
    if (!containerRef.current || limitedNodes.length === 0) return

    if (graphRef.current) {
      graphRef.current.destroy()
      graphRef.current = null
    }

    destroyedRef.current = false

    const container = containerRef.current
    const width = container.offsetWidth
    const height = Math.max(550, container.offsetHeight)

    // Detect mobile
    const isMobile = width < 640

    const graphData = {
      nodes: limitedNodes.map((node) => ({
        id: node.id,
        data: { ...node },
      })),
      edges: limitedEdges.map((edge, i) => ({
        id: `edge-${i}`,
        source: edge.source,
        target: edge.target,
        data: { ...edge },
      })),
    }

    const graph = new Graph({
      container,
      width,
      height,
      autoFit: 'view',
      padding: [50, 50, 50, 50],
      data: graphData,
      node: {
        type: 'rect',
        style: {
          size: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            if (nd.is_origin) return isMobile ? [200, 56] : [260, 64]
            return isMobile ? [170, 48] : [220, 56]
          },
          radius: 10,
          fill: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            const color = LIFECYCLE_COLORS[(nd.lifecycle_stage as LifecycleStage) || 'fadeout'] || '#6b7280'
            return nd.is_origin ? color + '30' : color + '18'
          },
          stroke: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            return LIFECYCLE_COLORS[(nd.lifecycle_stage as LifecycleStage) || 'fadeout'] || '#6b7280'
          },
          lineWidth: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            if (nd.is_origin) return 2.5
            if (nd.is_user_selected) return 2.5
            return 1.5
          },
          lineDash: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            return nd.is_user_selected && !nd.is_origin ? [6, 3] : undefined
          },
          shadowColor: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            if (nd.is_origin) return 'rgba(34, 197, 94, 0.35)'
            if (nd.lifecycle_stage === 'explosion') return 'rgba(239, 68, 68, 0.25)'
            return 'transparent'
          },
          shadowBlur: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            return nd.is_origin ? 14 : nd.lifecycle_stage === 'explosion' ? 10 : 0
          },
          labelText: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            const publisher = nd.publisher || '알 수 없음'
            const titleLen = isMobile ? 18 : 28
            if (nd.is_origin) {
              return `★ ${publisher}\n${truncate(nd.title, titleLen)}`
            }
            const prefix = nd.is_user_selected ? '◎ ' : ''
            const score = Math.round(nd.similarity_score * 100)
            return `${prefix}${publisher} · ${score}%\n${truncate(nd.title, titleLen)}`
          },
          labelFill: isDark ? '#e5e7eb' : '#1f2937',
          labelFontSize: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            return nd.is_origin ? 12 : 11
          },
          labelFontWeight: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            return nd.is_origin ? 'bold' : 'normal'
          },
          labelLineHeight: 16,
          labelPlacement: 'center',
          cursor: 'pointer',
        },
      },
      edge: {
        type: 'cubic-vertical',
        style: {
          stroke: (d: Record<string, unknown>) => {
            const ed = d.data as GraphEdge
            if (ed.similarity_category === 'same') return '#22c55e'
            if (ed.similarity_category === 'derivative') return '#3b82f6'
            return isDark ? '#6b7280' : '#9ca3af'
          },
          lineWidth: (d: Record<string, unknown>) => {
            const ed = d.data as GraphEdge
            if (ed.similarity_category === 'same') return 2.5
            if (ed.similarity_category === 'derivative') return 2
            return 1
          },
          lineDash: (d: Record<string, unknown>) => {
            const ed = d.data as GraphEdge
            return ed.similarity_category === 'related' ? [5, 5] : undefined
          },
          endArrow: true,
          endArrowSize: 7,
          opacity: 0.65,
          labelText: (d: Record<string, unknown>) => {
            const ed = d.data as GraphEdge
            return `${Math.round(ed.similarity_score * 100)}%`
          },
          labelFill: isDark ? '#9ca3af' : '#6b7280',
          labelFontSize: 9,
          labelBackgroundFill: isDark ? '#111827' : '#f9fafb',
          labelBackgroundRadius: 4,
          labelBackgroundOpacity: 0.85,
          labelPadding: [2, 4],
        },
      },
      layout: {
        type: 'dagre',
        rankdir: 'BT',
        nodesep: isMobile ? 25 : 40,
        ranksep: isMobile ? 55 : 75,
      },
      behaviors: [
        'zoom-canvas',
        'drag-canvas',
        'drag-element',
      ],
    })

    graphRef.current = graph

    graph.on('node:click', (evt) => {
      const nodeId = (evt as { target?: { id?: string } })?.target?.id
      if (nodeId) handleNodeClick(nodeId)
    })

    const rafId = requestAnimationFrame(() => {
      if (!destroyedRef.current && graphRef.current) {
        const renderPromise = graph.render()
        if (renderPromise && typeof renderPromise.catch === 'function') {
          renderPromise.catch(() => {})
        }
      }
    })

    const handleResize = () => {
      if (graphRef.current && containerRef.current && !destroyedRef.current) {
        graphRef.current.resize(
          containerRef.current.offsetWidth,
          Math.max(550, containerRef.current.offsetHeight),
        )
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      destroyedRef.current = true
      cancelAnimationFrame(rafId)
      window.removeEventListener('resize', handleResize)
      if (graphRef.current) {
        try {
          graphRef.current.destroy()
        } catch {
          // Already destroyed
        }
        graphRef.current = null
      }
    }
  }, [limitedNodes, limitedEdges, handleNodeClick, isDark])

  if (nodes.length === 0) {
    return (
      <div className="flex h-96 items-center justify-center text-muted-foreground">
        그래프 데이터가 없습니다.
      </div>
    )
  }

  return (
    <div className={`relative ${isFullscreen ? 'fixed inset-0 z-50 bg-background p-2 sm:p-4 md:p-6' : ''}`}>
      {/* Node limit warning */}
      {hasExcessNodes && (
        <div className="mb-3 flex flex-col gap-2 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2">
            <span className="text-yellow-400">⚠️</span>
            <div className="text-sm">
              <p className="font-medium text-yellow-400">
                노드가 {nodes.length}개로 많습니다
              </p>
              <p className="mt-0.5 text-xs text-yellow-400/80">
                {showAllNodes ? '전체' : `상위 ${NODE_LIMIT}개`} 노드 표시 중
                {!showAllNodes && ` (${nodes.length - NODE_LIMIT}개 숨김)`}
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowAllNodes(!showAllNodes)}
            className="shrink-0 rounded-md border border-yellow-500/40 bg-yellow-500/20 px-3 py-1.5 text-xs font-medium text-yellow-400 transition-colors hover:bg-yellow-500/30"
          >
            {showAllNodes ? '축소 모드' : '모두 표시'}
          </button>
        </div>
      )}

      <div
        ref={containerRef}
        className={`w-full rounded-xl border border-border bg-gray-50/50 dark:bg-gray-900/40 ${
          isFullscreen ? 'h-full' : className || 'h-[400px] sm:h-[600px]'
        }`}
        style={{ touchAction: 'none' }}
      />

      {/* Controls */}
      <div className="absolute right-2 top-2 flex flex-col gap-1 sm:right-3 sm:top-3">
        {([
          { action: handleZoomIn, icon: <ZoomIn className="h-4 w-4" />, label: '확대' },
          { action: handleZoomOut, icon: <ZoomOut className="h-4 w-4" />, label: '축소' },
          { action: handleFitView, icon: <span className="text-[10px] font-bold">FIT</span>, label: '전체보기' },
          { action: toggleFullscreen, icon: isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />, label: isFullscreen ? '축소' : '전체화면' },
        ] as const).map((ctrl, i) => (
          <button
            key={i}
            onClick={ctrl.action}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-border/50 bg-white/90 text-gray-500 shadow-sm backdrop-blur-sm transition-colors hover:bg-white hover:text-foreground dark:bg-gray-800/90 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
            aria-label={ctrl.label}
          >
            {ctrl.icon}
          </button>
        ))}
      </div>

      {/* Legend toggle */}
      <div className="absolute bottom-2 left-2 sm:bottom-3 sm:left-3">
        <button
          onClick={() => setShowLegend(!showLegend)}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-border/50 bg-white/90 text-gray-500 shadow-sm backdrop-blur-sm transition-colors hover:bg-white hover:text-foreground dark:bg-gray-800/90 dark:text-gray-400 dark:hover:bg-gray-800"
          aria-label="범례"
        >
          <Info className="h-4 w-4" />
        </button>
        {showLegend && (
          <div className="mt-1.5 min-w-[180px] rounded-lg border border-border/50 bg-white/95 p-2.5 shadow-lg backdrop-blur-sm dark:bg-gray-800/95">
            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">라이프사이클</p>
            <div className="space-y-1">
              {(['origin', 'spread', 'explosion', 'sustained', 'fadeout'] as LifecycleStage[]).map(
                (stage) => (
                  <div key={stage} className="flex items-center gap-2">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full ring-1 ring-black/10"
                      style={{ backgroundColor: LIFECYCLE_COLORS[stage] }}
                    />
                    <span className="text-[11px] text-foreground/70">
                      {LIFECYCLE_LABELS[stage]}
                    </span>
                  </div>
                ),
              )}
            </div>
            <div className="my-2 border-t border-border/50" />
            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">유사도</p>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="inline-block h-0.5 w-5 rounded bg-green-500" />
                <span className="text-[11px] text-foreground/70">동일 (80%+)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-block h-0.5 w-5 rounded bg-blue-500" />
                <span className="text-[11px] text-foreground/70">파생 (65-80%)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-block h-0.5 w-5 rounded border-t-2 border-dashed border-gray-400" />
                <span className="text-[11px] text-foreground/70">관련 (52-65%)</span>
              </div>
            </div>
            <div className="my-2 border-t border-border/50" />
            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">노드</p>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-[11px]">★</span>
                <span className="text-[11px] text-foreground/70">기원 기사</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px]">◎</span>
                <span className="text-[11px] text-foreground/70">내가 선택한 기사</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Fullscreen indicator */}
      {isFullscreen && (
        <div className="absolute left-1/2 top-2 -translate-x-1/2 rounded-lg border border-border/50 bg-white/90 px-3 py-1.5 text-xs text-muted-foreground shadow-sm backdrop-blur-sm dark:bg-gray-800/90">
          ESC로 전체화면 종료
        </div>
      )}
    </div>
  )
}
