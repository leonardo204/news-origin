import { useEffect, useRef, useCallback, useState, useMemo } from 'react'
import { ZoomIn, ZoomOut, Maximize2, Minimize2 } from 'lucide-react'
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
  const [showLegend, setShowLegend] = useState(true)
  const [showAllNodes, setShowAllNodes] = useState(false)

  // Limit nodes to top 50 by similarity_score when count exceeds 50
  const NODE_LIMIT = 50
  const hasExcessNodes = nodes.length > NODE_LIMIT
  const limitedNodes = useMemo(() => {
    if (!hasExcessNodes || showAllNodes) return nodes
    // Always include origin node + top 49 by similarity_score
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

  // ESC to exit fullscreen — must be before any early return
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

  useEffect(() => {
    if (!containerRef.current || limitedNodes.length === 0) return

    // Clean up previous graph
    if (graphRef.current) {
      graphRef.current.destroy()
      graphRef.current = null
    }

    destroyedRef.current = false

    const container = containerRef.current
    const width = container.offsetWidth
    const height = Math.max(550, container.offsetHeight)

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
      padding: [40, 40, 40, 40],
      data: graphData,
      node: {
        type: 'rect',
        style: {
          size: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            return nd.is_origin ? [160, 48] : [140, 40]
          },
          radius: 8,
          fill: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            const color = LIFECYCLE_COLORS[(nd.lifecycle_stage as LifecycleStage) || 'fadeout'] || '#6b7280'
            return color + '20' // 12% opacity fill
          },
          stroke: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            return LIFECYCLE_COLORS[(nd.lifecycle_stage as LifecycleStage) || 'fadeout'] || '#6b7280'
          },
          lineWidth: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            return nd.is_origin ? 2.5 : 1.5
          },
          shadowColor: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            if (nd.is_origin) return 'rgba(34, 197, 94, 0.3)'
            if (nd.lifecycle_stage === 'explosion') return 'rgba(239, 68, 68, 0.2)'
            return 'transparent'
          },
          shadowBlur: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            return nd.is_origin || nd.lifecycle_stage === 'explosion' ? 10 : 0
          },
          labelText: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            const publisher = nd.publisher || (nd.url ? new URL(nd.url).hostname.replace('www.', '') : '알 수 없음')
            if (nd.is_origin) return `[기원] ${publisher}`
            return `${publisher}\n${truncate(nd.title, 16)}`
          },
          labelFill: '#e5e7eb',
          labelFontSize: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            return nd.is_origin ? 11 : 10
          },
          labelFontWeight: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            return nd.is_origin ? 'bold' : 'normal'
          },
          labelLineHeight: 14,
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
            return '#4b5563'
          },
          lineWidth: (d: Record<string, unknown>) => {
            const ed = d.data as GraphEdge
            if (ed.similarity_category === 'same') return 2.5
            if (ed.similarity_category === 'derivative') return 1.5
            return 1
          },
          lineDash: (d: Record<string, unknown>) => {
            const ed = d.data as GraphEdge
            return ed.similarity_category === 'related' ? [4, 4] : undefined
          },
          endArrow: true,
          endArrowSize: 6,
          opacity: 0.7,
        },
      },
      layout: {
        type: 'dagre',
        rankdir: 'TB',
        nodesep: 30,
        ranksep: 60,
      },
      behaviors: [
        'zoom-canvas',
        'drag-canvas',
        'drag-element',
      ],
    })

    // Set ref BEFORE render so cleanup can always find it
    graphRef.current = graph

    // Click handler
    graph.on('node:click', (evt) => {
      const nodeId = (evt as { target?: { id?: string } })?.target?.id
      if (nodeId) handleNodeClick(nodeId)
    })

    // Defer render to next frame so React StrictMode cleanup can cancel it
    const rafId = requestAnimationFrame(() => {
      if (!destroyedRef.current && graphRef.current) {
        const renderPromise = graph.render()
        if (renderPromise && typeof renderPromise.catch === 'function') {
          renderPromise.catch(() => {
            // Graph was destroyed before render completed — safe to ignore
          })
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
          // Already destroyed — safe to ignore
        }
        graphRef.current = null
      }
    }
  }, [limitedNodes, limitedEdges, handleNodeClick])

  if (nodes.length === 0) {
    return (
      <div className="flex h-96 items-center justify-center text-muted-foreground">
        그래프 데이터가 없습니다.
      </div>
    )
  }

  return (
    <div className={`relative ${isFullscreen ? 'fixed inset-0 z-50 bg-background p-4 sm:p-6 md:p-8' : ''}`}>
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
                성능 보호를 위해 {showAllNodes ? '전체' : `상위 ${NODE_LIMIT}개`} 노드를 표시 중입니다
                {!showAllNodes && ` (${nodes.length - NODE_LIMIT}개 숨김)`}
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowAllNodes(!showAllNodes)}
            className="shrink-0 rounded-md border border-yellow-500/40 bg-yellow-500/20 px-3 py-1.5 text-xs font-medium text-yellow-400 transition-colors hover:bg-yellow-500/30"
            aria-label={showAllNodes ? '상위 50개만 보기' : '모두 표시'}
          >
            {showAllNodes ? '축소 모드' : '모두 표시'}
          </button>
        </div>
      )}

      <div
        ref={containerRef}
        className={`w-full rounded-lg border border-border bg-gray-100/30 dark:bg-gray-900/30 ${
          isFullscreen ? 'h-full' : className || 'h-[400px] sm:h-[600px]'
        }`}
        style={{ touchAction: 'none' }}
      />

      {/* Zoom controls */}
      <div className="absolute right-3 top-3 flex flex-col gap-1">
        <button
          onClick={handleZoomIn}
          className="rounded-md bg-gray-100/80 p-1.5 text-gray-600 backdrop-blur-sm hover:text-foreground dark:bg-gray-900/80 dark:text-gray-400"
          aria-label="확대"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          onClick={handleZoomOut}
          className="rounded-md bg-gray-100/80 p-1.5 text-gray-600 backdrop-blur-sm hover:text-foreground dark:bg-gray-900/80 dark:text-gray-400"
          aria-label="축소"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <button
          onClick={handleFitView}
          className="rounded-md bg-gray-100/80 p-1.5 text-xs text-gray-600 backdrop-blur-sm hover:text-foreground dark:bg-gray-900/80 dark:text-gray-400"
          aria-label="전체보기"
        >
          FIT
        </button>
        <button
          onClick={toggleFullscreen}
          className="rounded-md bg-gray-100/80 p-1.5 text-gray-600 backdrop-blur-sm hover:text-foreground dark:bg-gray-900/80 dark:text-gray-400"
          aria-label={isFullscreen ? '전체화면 종료' : '전체화면'}
        >
          {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </button>
      </div>

      {/* Legend (collapsible) */}
      <div className="absolute bottom-3 left-3">
        <button
          onClick={() => setShowLegend(!showLegend)}
          className="mb-1 rounded-md bg-gray-100/80 px-2 py-1 text-[10px] text-gray-600 backdrop-blur-sm hover:text-foreground dark:bg-gray-900/80 dark:text-gray-400"
        >
          {showLegend ? '범례 숨기기' : '범례'}
        </button>
        {showLegend && (
          <div className="flex flex-wrap gap-2 rounded-lg bg-gray-100/80 p-2 backdrop-blur-sm dark:bg-gray-900/80">
            {(['origin', 'spread', 'explosion', 'sustained', 'fadeout'] as LifecycleStage[]).map(
              (stage) => (
                <div key={stage} className="flex items-center gap-1">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: LIFECYCLE_COLORS[stage] }}
                  />
                  <span className="text-[10px] text-gray-600 dark:text-gray-400">
                    {LIFECYCLE_LABELS[stage]}
                  </span>
                </div>
              ),
            )}
            <div className="ml-2 flex items-center gap-1">
              <span className="inline-block h-px w-4 bg-green-500" />
              <span className="text-[10px] text-gray-600 dark:text-gray-400">동일</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="inline-block h-px w-4 bg-blue-500" />
              <span className="text-[10px] text-gray-600 dark:text-gray-400">파생</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="inline-block h-px w-4 border-t border-dashed border-gray-500" />
              <span className="text-[10px] text-gray-600 dark:text-gray-400">관련</span>
            </div>
          </div>
        )}
      </div>

      {/* ESC to exit fullscreen */}
      {isFullscreen && (
        <div className="absolute left-1/2 top-3 -translate-x-1/2 rounded-md bg-gray-100/80 px-3 py-1 text-xs text-gray-600 backdrop-blur-sm dark:bg-gray-900/80 dark:text-gray-400">
          ESC 또는 버튼으로 전체화면 종료
        </div>
      )}
    </div>
  )
}
