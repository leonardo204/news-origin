import { useEffect, useRef, useCallback, useState } from 'react'
import { ZoomIn, ZoomOut, Maximize2, Minimize2 } from 'lucide-react'
import { Graph } from '@antv/g6'
import { LIFECYCLE_COLORS, LIFECYCLE_LABELS, truncate } from '@/lib/utils'
import type { GraphNode, GraphEdge, LifecycleStage } from '@/types'

interface PropagationGraphProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  onNodeClick?: (node: GraphNode) => void
}

export default function PropagationGraph({ nodes, edges, onNodeClick }: PropagationGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<Graph | null>(null)
  const destroyedRef = useRef(false)
  const nodesRef = useRef(nodes)
  nodesRef.current = nodes
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showLegend, setShowLegend] = useState(true)

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
    if (!containerRef.current || nodes.length === 0) return

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
      nodes: nodes.map((node) => ({
        id: node.id,
        data: { ...node },
      })),
      edges: edges.map((edge, i) => ({
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
        type: 'circle',
        style: {
          size: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            if (nd.is_origin) return 44
            const base = 20
            const bonus = nd.similarity_score * 18
            return base + bonus
          },
          fill: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            return LIFECYCLE_COLORS[(nd.lifecycle_stage as LifecycleStage) || 'fadeout'] || '#6b7280'
          },
          fillOpacity: 0.85,
          stroke: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            if (nd.is_origin) return '#ffffff'
            return LIFECYCLE_COLORS[(nd.lifecycle_stage as LifecycleStage) || 'fadeout'] || '#6b7280'
          },
          lineWidth: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            return nd.is_origin ? 3 : 1
          },
          shadowColor: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            if (nd.is_origin) return 'rgba(34, 197, 94, 0.4)'
            if (nd.lifecycle_stage === 'explosion') return 'rgba(239, 68, 68, 0.3)'
            return 'transparent'
          },
          shadowBlur: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            return nd.is_origin || nd.lifecycle_stage === 'explosion' ? 12 : 0
          },
          labelText: (d: Record<string, unknown>) => {
            const nd = d.data as GraphNode
            if (nd.is_origin) return `[기원] ${nd.publisher || ''}`
            return nd.publisher || truncate(nd.title, 12)
          },
          labelFill: '#d1d5db',
          labelFontSize: 10,
          labelPlacement: 'bottom',
          labelOffsetY: 6,
          cursor: 'pointer',
        },
      },
      edge: {
        type: 'line',
        style: {
          stroke: (d: Record<string, unknown>) => {
            const ed = d.data as GraphEdge
            if (ed.similarity_category === 'same') return '#22c55e'
            if (ed.similarity_category === 'derivative') return '#3b82f6'
            return '#374151'
          },
          lineWidth: (d: Record<string, unknown>) => {
            const ed = d.data as GraphEdge
            return ed.similarity_category === 'same' ? 2 : 1
          },
          lineDash: (d: Record<string, unknown>) => {
            const ed = d.data as GraphEdge
            return ed.similarity_category === 'related' ? [4, 4] : undefined
          },
          endArrow: true,
          endArrowSize: 6,
          opacity: 0.6,
        },
      },
      layout: {
        type: 'force',
        preventOverlap: true,
        nodeSize: 60,
        nodeSpacing: 40,
        nodeStrength: -800,
        edgeStrength: 0.2,
        linkDistance: (edge: Record<string, unknown>) => {
          const ed = (edge as { data: GraphEdge }).data
          if (ed?.similarity_category === 'same') return 160
          if (ed?.similarity_category === 'derivative') return 240
          return 320
        },
        alpha: 0.3,
        alphaDecay: 0.06,
        alphaMin: 0.01,
        collideStrength: 1.0,
        maxIteration: 800,
        animated: false,
      },
      behaviors: [
        'zoom-canvas',
        'drag-canvas',
        { type: 'drag-element', enable: true },
      ],
    })

    // Set ref BEFORE render so cleanup can always find it
    graphRef.current = graph

    // Click handler
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    graph.on('node:click', (evt: any) => {
      const nodeId = evt?.target?.id
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
  }, [nodes, edges, handleNodeClick])

  if (nodes.length === 0) {
    return (
      <div className="flex h-96 items-center justify-center text-muted-foreground">
        그래프 데이터가 없습니다.
      </div>
    )
  }

  return (
    <div className={`relative ${isFullscreen ? 'fixed inset-0 z-50 bg-background p-4' : ''}`}>
      <div
        ref={containerRef}
        className={`w-full rounded-lg border border-border bg-gray-900/30 ${
          isFullscreen ? 'h-full' : 'h-[400px] sm:h-[600px]'
        }`}
      />

      {/* Zoom controls */}
      <div className="absolute right-3 top-3 flex flex-col gap-1">
        <button
          onClick={handleZoomIn}
          className="rounded-md bg-gray-900/80 p-1.5 text-gray-400 backdrop-blur-sm hover:text-white"
          aria-label="확대"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          onClick={handleZoomOut}
          className="rounded-md bg-gray-900/80 p-1.5 text-gray-400 backdrop-blur-sm hover:text-white"
          aria-label="축소"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <button
          onClick={handleFitView}
          className="rounded-md bg-gray-900/80 p-1.5 text-xs text-gray-400 backdrop-blur-sm hover:text-white"
          aria-label="전체보기"
        >
          FIT
        </button>
        <button
          onClick={toggleFullscreen}
          className="rounded-md bg-gray-900/80 p-1.5 text-gray-400 backdrop-blur-sm hover:text-white"
          aria-label={isFullscreen ? '전체화면 종료' : '전체화면'}
        >
          {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </button>
      </div>

      {/* Legend (collapsible) */}
      <div className="absolute bottom-3 left-3">
        <button
          onClick={() => setShowLegend(!showLegend)}
          className="mb-1 rounded-md bg-gray-900/80 px-2 py-1 text-[10px] text-gray-400 backdrop-blur-sm hover:text-white"
        >
          {showLegend ? '범례 숨기기' : '범례'}
        </button>
        {showLegend && (
          <div className="flex flex-wrap gap-2 rounded-lg bg-gray-900/80 p-2 backdrop-blur-sm">
            {(['origin', 'spread', 'explosion', 'sustained', 'fadeout'] as LifecycleStage[]).map(
              (stage) => (
                <div key={stage} className="flex items-center gap-1">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: LIFECYCLE_COLORS[stage] }}
                  />
                  <span className="text-[10px] text-gray-400">
                    {LIFECYCLE_LABELS[stage]}
                  </span>
                </div>
              ),
            )}
            <div className="ml-2 flex items-center gap-1">
              <span className="inline-block h-px w-4 bg-green-500" />
              <span className="text-[10px] text-gray-400">동일</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="inline-block h-px w-4 bg-blue-500" />
              <span className="text-[10px] text-gray-400">파생</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="inline-block h-px w-4 border-t border-dashed border-gray-500" />
              <span className="text-[10px] text-gray-400">관련</span>
            </div>
          </div>
        )}
      </div>

      {/* ESC to exit fullscreen */}
      {isFullscreen && (
        <div className="absolute left-1/2 top-3 -translate-x-1/2 rounded-md bg-gray-900/80 px-3 py-1 text-xs text-gray-400 backdrop-blur-sm">
          ESC 또는 버튼으로 전체화면 종료
        </div>
      )}
    </div>
  )
}
