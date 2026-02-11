import { X, ExternalLink, Building2, Clock, Percent } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import {
  formatDate,
  LIFECYCLE_LABELS,
  SIMILARITY_LABELS,
} from '@/lib/utils'
import type { GraphNode, LifecycleStage, SimilarityCategory } from '@/types'

interface ArticleDetailPanelProps {
  node: GraphNode | null
  onClose: () => void
}

export default function ArticleDetailPanel({ node, onClose }: ArticleDetailPanelProps) {
  if (!node) return null

  return (
    <div className="absolute inset-0 z-10 overflow-y-auto border-l border-border bg-card p-4 shadow-lg sm:inset-auto sm:right-0 sm:top-0 sm:h-full sm:w-80">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-muted-foreground">기사 상세</h3>
        <button
          onClick={onClose}
          className="rounded-md p-1 hover:bg-secondary"
          aria-label="상세 패널 닫기"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <div className="space-y-4">
        {/* Title */}
        <div>
          <h2 className="text-sm font-semibold leading-tight">{node.title}</h2>
          {node.url && (
            <a
              href={node.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 inline-flex items-center gap-1 text-xs text-lifecycle-origin hover:underline"
            >
              <ExternalLink className="h-3 w-3" />
              원문 보기
            </a>
          )}
        </div>

        {/* Metadata */}
        <div className="space-y-2 text-sm">
          {node.publisher && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Building2 className="h-3.5 w-3.5 shrink-0" />
              <span>{node.publisher}</span>
            </div>
          )}
          {node.published_at && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Clock className="h-3.5 w-3.5 shrink-0" />
              <span>{formatDate(node.published_at)}</span>
            </div>
          )}
        </div>

        {/* Badges */}
        <div className="flex flex-wrap gap-2">
          {node.lifecycle_stage && (
            <Badge stage={node.lifecycle_stage as LifecycleStage}>
              {LIFECYCLE_LABELS[node.lifecycle_stage as LifecycleStage]}
            </Badge>
          )}
          {node.similarity_category && (
            <Badge>
              {SIMILARITY_LABELS[node.similarity_category as SimilarityCategory]}
            </Badge>
          )}
          {node.is_origin && (
            <Badge stage="origin">기원</Badge>
          )}
        </div>

        {/* Similarity Score */}
        <div className="rounded-md bg-secondary/50 p-3">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Percent className="h-3.5 w-3.5" />
            유사도
          </div>
          <div className="mt-1 flex items-end gap-1">
            <span className="text-2xl font-bold tabular-nums">
              {(node.similarity_score * 100).toFixed(1)}
            </span>
            <span className="mb-1 text-sm text-muted-foreground">%</span>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full rounded-full bg-lifecycle-origin transition-all"
              style={{ width: `${node.similarity_score * 100}%` }}
            />
          </div>
        </div>

        {/* Open article */}
        {node.url && (
          <Button
            variant="outline"
            className="w-full"
            onClick={() => window.open(node.url!, '_blank', 'noopener,noreferrer')}
          >
            <ExternalLink className="mr-1.5 h-4 w-4" />
            기사 원문 열기
          </Button>
        )}
      </div>
    </div>
  )
}
