import { useState, useMemo, useCallback, useRef } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  Position,
  Handle,
  MarkerType,
  type Node,
  type Edge,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from '@dagrejs/dagre'
import { Info } from 'lucide-react'
import { LIFECYCLE_COLORS, LIFECYCLE_LABELS, truncate } from '@/lib/utils'
import type { GraphNode, GraphEdge, LifecycleStage } from '@/types'

interface PropagationGraphProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  onNodeClick?: (node: GraphNode) => void
  className?: string
}

const NODE_LIMIT = 50
const NODE_W = 300
const NODE_H = 108
const ORIGIN_W = 320
const ORIGIN_H = 114
const DAGRE_PAD = 28
const MAX_COLS_PER_ROW = 4
const COL_WIDTH = NODE_W + 180
const ROW_GAP = 200

/* ─── Helpers ─── */

function getNodeColor(n: GraphNode): string {
  if (n.is_origin) return '#22c55e'
  return LIFECYCLE_COLORS[(n.lifecycle_stage as LifecycleStage) || 'fadeout'] || '#6b7280'
}

function edgeColor(e: GraphEdge, isDark: boolean): string {
  if (e.similarity_category === 'same') return '#22c55e'
  if (e.similarity_category === 'derivative') return '#3b82f6'
  return isDark ? '#6b7280' : '#9ca3af'
}

function edgeWidth(e: GraphEdge): number {
  if (e.similarity_category === 'same') return 2.5
  if (e.similarity_category === 'derivative') return 2
  return 1
}

/* ─── Serpentine dagre layout ─── */

function layoutGraph(graphNodes: GraphNode[], graphEdges: GraphEdge[], isDark: boolean) {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'LR', nodesep: 80, ranksep: 180 })

  graphNodes.forEach((n) => {
    const w = n.is_origin ? ORIGIN_W : NODE_W
    const h = n.is_origin ? ORIGIN_H : NODE_H
    g.setNode(n.id, { width: w + DAGRE_PAD, height: h + DAGRE_PAD })
  })
  graphEdges.forEach((e) => g.setEdge(e.source, e.target))
  dagre.layout(g)

  const dagrePos = new Map<string, { x: number; y: number }>()
  graphNodes.forEach((n) => {
    const p = g.node(n.id)
    dagrePos.set(n.id, { x: p.x, y: p.y })
  })

  const allXs = [...new Set([...dagrePos.values()].map((p) => p.x))].sort((a, b) => a - b)
  const xToCol = new Map<number, number>()
  allXs.forEach((x, i) => xToCol.set(x, i))

  const totalCols = allXs.length
  const needsWrap = totalCols > MAX_COLS_PER_ROW

  interface RowInfo { minY: number; maxY: number }
  const rowMap = new Map<number, RowInfo>()

  graphNodes.forEach((n) => {
    const pos = dagrePos.get(n.id)!
    const col = xToCol.get(pos.x) || 0
    const rowIdx = needsWrap ? Math.floor(col / MAX_COLS_PER_ROW) : 0
    const h = n.is_origin ? ORIGIN_H : NODE_H
    const row = rowMap.get(rowIdx) || { minY: Infinity, maxY: -Infinity }
    row.minY = Math.min(row.minY, pos.y - h / 2)
    row.maxY = Math.max(row.maxY, pos.y + h / 2)
    rowMap.set(rowIdx, row)
  })

  const rowOffsets = new Map<number, { yOffset: number; minY: number }>()
  let cumulativeY = 0
  const sortedRows = [...rowMap.keys()].sort((a, b) => a - b)
  for (const rowIdx of sortedRows) {
    const row = rowMap.get(rowIdx)!
    rowOffsets.set(rowIdx, { yOffset: cumulativeY, minY: row.minY })
    cumulativeY += row.maxY - row.minY + ROW_GAP
  }

  const nodes: Node[] = graphNodes.map((n) => {
    const pos = dagrePos.get(n.id)!
    const col = xToCol.get(pos.x) || 0
    const w = n.is_origin ? ORIGIN_W : NODE_W
    const h = n.is_origin ? ORIGIN_H : NODE_H
    const color = getNodeColor(n)

    let finalX: number
    let finalY: number

    if (needsWrap) {
      const rowIdx = Math.floor(col / MAX_COLS_PER_ROW)
      const colInRow = col % MAX_COLS_PER_ROW
      const offsets = rowOffsets.get(rowIdx)!
      finalX = colInRow * COL_WIDTH
      finalY = (pos.y - offsets.minY) + offsets.yOffset
    } else {
      finalX = pos.x
      finalY = pos.y
    }

    return {
      id: n.id,
      type: n.is_origin ? 'origin' : 'article',
      position: { x: finalX - w / 2, y: finalY - h / 2 },
      data: { ...n },
      style: { background: color, width: w, height: h },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    }
  })

  const edges: Edge[] = graphEdges.map((e, i) => ({
    id: `e-${i}`,
    source: e.source,
    target: e.target,
    type: 'smoothstep',
    animated: e.similarity_category === 'same',
    style: {
      stroke: edgeColor(e, isDark),
      strokeWidth: edgeWidth(e),
      strokeDasharray: e.similarity_category === 'related' ? '5 5' : undefined,
      opacity: 0.7,
    },
    markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor(e, isDark) },
    label: `${Math.round(e.similarity_score * 100)}%`,
    labelStyle: { fontSize: 11, fontWeight: 600, fill: isDark ? '#d1d5db' : '#4b5563' },
    labelBgStyle: { fill: isDark ? '#1f2937' : '#ffffff', opacity: 0.9 },
    labelBgPadding: [6, 8] as [number, number],
    labelBgBorderRadius: 6,
  }))

  return { nodes, edges }
}

/* ─── Custom node components ─── */

function OriginNode({ data }: NodeProps) {
  const d = data as unknown as GraphNode
  return (
    <div
      className="flex overflow-hidden rounded-xl bg-white shadow-lg dark:bg-gray-900"
      style={{ width: ORIGIN_W, minHeight: ORIGIN_H, boxShadow: '0 4px 16px rgba(34,197,94,0.18)' }}
    >
      <div className="w-2 shrink-0 bg-lifecycle-origin" />
      <div className="flex-1 px-4 py-3">
        <Handle type="source" position={Position.Right} className="!h-3 !w-3 !border-2 !border-white !bg-lifecycle-origin" />
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-full bg-lifecycle-origin/15 px-2 py-0.5 text-xs font-bold text-lifecycle-origin">
            ★ 기원
          </span>
          <span className="text-sm text-muted-foreground">{d.publisher || '알 수 없음'}</span>
        </div>
        <p className="mt-2 text-[15px] font-semibold leading-snug text-foreground">
          {truncate(d.title, 50)}
        </p>
      </div>
    </div>
  )
}

function ArticleNode({ data }: NodeProps) {
  const d = data as unknown as GraphNode
  const color = LIFECYCLE_COLORS[(d.lifecycle_stage as LifecycleStage) || 'fadeout'] || '#6b7280'
  const label = LIFECYCLE_LABELS[(d.lifecycle_stage as LifecycleStage) || 'fadeout'] || ''
  const score = Math.round(d.similarity_score * 100)

  return (
    <div
      className="flex overflow-hidden rounded-xl bg-white dark:bg-gray-900"
      style={{
        width: NODE_W,
        minHeight: NODE_H,
        boxShadow: `0 2px 12px ${color}22`,
        outline: d.is_user_selected ? `2.5px solid #3b82f6` : undefined,
        border: d.is_user_selected ? undefined : `1px solid ${color}35`,
      }}
    >
      <div className="w-2 shrink-0" style={{ backgroundColor: color }} />
      <div className="flex-1 px-4 py-3">
        <Handle type="target" position={Position.Left} className="!h-3 !w-3 !border-2 !border-white !bg-gray-400 dark:!border-gray-900" />
        <Handle type="source" position={Position.Right} className="!h-3 !w-3 !border-2 !border-white !bg-gray-400 dark:!border-gray-900" />
        <div className="flex items-center gap-2">
          {d.is_user_selected && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-blue-500/15 px-2 py-0.5 text-[11px] font-bold text-blue-500">◎ 대표</span>
          )}
          <span className="text-sm font-medium text-foreground/70">{d.publisher || '알 수 없음'}</span>
          <span className="text-sm text-muted-foreground/50">·</span>
          <span
            className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold"
            style={{ backgroundColor: color + '18', color }}
          >
            {score}%
          </span>
          {label && (
            <span className="text-[11px] text-muted-foreground">{label}</span>
          )}
        </div>
        <p className="mt-2 text-[15px] leading-snug text-foreground">
          {truncate(d.title, 50)}
        </p>
      </div>
    </div>
  )
}

const nodeTypes = { origin: OriginNode, article: ArticleNode }

/* ─── Main component ─── */

export default function PropagationGraph({ nodes, edges, onNodeClick, className }: PropagationGraphProps) {
  const [showLegend, setShowLegend] = useState(false)
  const [showAllNodes, setShowAllNodes] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const isDark = typeof document !== 'undefined' && document.documentElement.classList.contains('dark')

  const hasExcessNodes = nodes.length > NODE_LIMIT
  const limitedNodes = useMemo(() => {
    if (!hasExcessNodes || showAllNodes) return nodes
    const origin = nodes.find((n) => n.is_origin)
    const nonOrigin = nodes
      .filter((n) => !n.is_origin)
      .sort((a, b) => (b.similarity_score || 0) - (a.similarity_score || 0))
      .slice(0, NODE_LIMIT - (origin ? 1 : 0))
    return origin ? [origin, ...nonOrigin] : nonOrigin
  }, [nodes, hasExcessNodes, showAllNodes])

  const limitedEdges = useMemo(() => {
    if (!hasExcessNodes || showAllNodes) return edges
    const nodeIds = new Set(limitedNodes.map((n) => n.id))
    return edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
  }, [edges, limitedNodes, hasExcessNodes, showAllNodes])

  const { nodes: rfNodes, edges: rfEdges } = useMemo(
    () => layoutGraph(limitedNodes, limitedEdges, isDark),
    [limitedNodes, limitedEdges, isDark],
  )

  // Fit horizontally only: all nodes visible left-right, vertical overflow OK
  const handleInit = useCallback((instance: { getNodes: () => Node[]; setViewport: (vp: { x: number; y: number; zoom: number }) => void }) => {
    setTimeout(() => {
      const allNodes = instance.getNodes()
      if (allNodes.length === 0 || !containerRef.current) return

      const cw = containerRef.current.clientWidth

      let minX = Infinity, maxX = -Infinity
      for (const n of allNodes) {
        const w = (typeof n.style?.width === 'number' ? n.style.width : NODE_W)
        minX = Math.min(minX, n.position.x)
        maxX = Math.max(maxX, n.position.x + w)
      }

      const graphWidth = maxX - minX
      const pad = 0.08
      const zoom = Math.min(cw / (graphWidth * (1 + pad * 2)), 0.85)

      const centerX = (minX + maxX) / 2
      const viewportX = cw / 2 - centerX * zoom
      const viewportY = 30

      instance.setViewport({ x: viewportX, y: viewportY, zoom })
    }, 60)
  }, [])

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const graphNode = node.data as unknown as GraphNode
      if (onNodeClick) {
        onNodeClick(graphNode)
      } else if (graphNode.url) {
        window.open(graphNode.url, '_blank', 'noopener,noreferrer')
      }
    },
    [onNodeClick],
  )

  if (nodes.length === 0) {
    return (
      <div className="flex h-96 items-center justify-center text-muted-foreground">
        그래프 데이터가 없습니다.
      </div>
    )
  }

  return (
    <div ref={containerRef} className={`relative ${className || 'h-full'}`}>
      {/* Node limit warning */}
      {hasExcessNodes && (
        <div className="absolute left-3 top-3 z-10 flex items-center gap-2 rounded-xl border border-yellow-500/30 bg-yellow-500/10 px-3 py-2 backdrop-blur-sm">
          <div className="text-xs">
            <span className="font-medium text-yellow-400">
              {showAllNodes ? '전체' : `상위 ${NODE_LIMIT}개`} / {nodes.length}개 노드
            </span>
          </div>
          <button
            onClick={() => setShowAllNodes(!showAllNodes)}
            className="rounded-lg border border-yellow-500/40 bg-yellow-500/20 px-2.5 py-1 text-xs font-medium text-yellow-400 transition-colors hover:bg-yellow-500/30"
          >
            {showAllNodes ? '축소' : '전체'}
          </button>
        </div>
      )}

      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        onInit={handleInit}
        panOnScroll
        minZoom={0.15}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
        nodesDraggable
        nodesConnectable={false}
      >
        <Background gap={28} size={1} color={isDark ? '#374151' : '#e5e7eb'} />
        <Controls
          position="top-right"
          showInteractive={false}
          style={{ borderRadius: 12 }}
        />
      </ReactFlow>

      {/* Legend toggle */}
      <div className="absolute bottom-2 left-2 z-10 sm:bottom-3 sm:left-3">
        <button
          onClick={() => setShowLegend(!showLegend)}
          className="flex h-9 w-9 items-center justify-center rounded-xl border border-border/50 bg-white/90 text-gray-500 shadow-sm backdrop-blur-sm transition-colors hover:bg-white hover:text-foreground dark:bg-gray-800/90 dark:text-gray-400 dark:hover:bg-gray-800"
          aria-label="범례"
        >
          <Info className="h-4 w-4" />
        </button>
        {showLegend && (
          <div className="mt-1.5 min-w-[200px] rounded-xl border border-border/50 bg-white/95 p-3 shadow-lg backdrop-blur-sm dark:bg-gray-800/95">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">라이프사이클</p>
            <div className="space-y-1.5">
              {(['origin', 'spread', 'explosion', 'sustained', 'fadeout'] as LifecycleStage[]).map(
                (stage) => (
                  <div key={stage} className="flex items-center gap-2.5">
                    <span
                      className="inline-block h-3 w-3 rounded-full ring-1 ring-black/10"
                      style={{ backgroundColor: LIFECYCLE_COLORS[stage] }}
                    />
                    <span className="text-xs text-foreground/70">
                      {LIFECYCLE_LABELS[stage]}
                    </span>
                  </div>
                ),
              )}
            </div>
            <div className="my-2.5 border-t border-border/50" />
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">유사도</p>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2.5">
                <span className="inline-block h-0.5 w-6 rounded bg-green-500" />
                <span className="text-xs text-foreground/70">동일 (80%+)</span>
              </div>
              <div className="flex items-center gap-2.5">
                <span className="inline-block h-0.5 w-6 rounded bg-blue-500" />
                <span className="text-xs text-foreground/70">파생 (65-80%)</span>
              </div>
              <div className="flex items-center gap-2.5">
                <span className="inline-block h-0.5 w-6 rounded border-t-2 border-dashed border-gray-400" />
                <span className="text-xs text-foreground/70">관련 (52-65%)</span>
              </div>
            </div>
            <div className="my-2.5 border-t border-border/50" />
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">노드</p>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2.5">
                <span className="text-xs font-bold text-lifecycle-origin">★</span>
                <span className="text-xs text-foreground/70">기원 기사</span>
              </div>
              <div className="flex items-center gap-2.5">
                <span className="text-xs font-bold text-blue-500">◎</span>
                <span className="text-xs text-foreground/70">대표 기사</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
