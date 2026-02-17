import { useState, useEffect } from 'react'
import { X, ExternalLink, Building2, Clock, Percent, Loader2, AlertCircle } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import BookmarkButton from '@/components/ui/BookmarkButton'
import { getArticle } from '@/services/api'
import {
  formatDate,
  LIFECYCLE_LABELS,
  SIMILARITY_LABELS,
} from '@/lib/utils'
import type { GraphNode, LifecycleStage, SimilarityCategory, Article } from '@/types'

interface ArticleDetailPanelProps {
  node: GraphNode | null
  onClose: () => void
}

export default function ArticleDetailPanel({ node, onClose }: ArticleDetailPanelProps) {
  const [articleDetail, setArticleDetail] = useState<Article | null>(null)
  const [isLoadingDetail, setIsLoadingDetail] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)

  useEffect(() => {
    if (!node) return

    setIsLoadingDetail(true)
    setDetailError(null)
    setArticleDetail(null)

    getArticle(node.id)
      .then((article) => {
        setArticleDetail(article)
        setIsLoadingDetail(false)
      })
      .catch((error) => {
        console.error('Failed to load article detail:', error)
        setDetailError('본문을 불러올 수 없습니다.')
        setIsLoadingDetail(false)
      })
  }, [node?.id])

  if (!node) return null

  const contentPreview = articleDetail?.content
    ? articleDetail.content.length > 300
      ? articleDetail.content.slice(0, 300) + '...'
      : articleDetail.content
    : null

  return (
    <>
      {/* Backdrop on mobile */}
      <div
        className="absolute inset-0 z-10 bg-black/30 backdrop-blur-[2px] sm:hidden"
        onClick={onClose}
      />
      {/* Panel: bottom sheet on mobile, right sidebar on desktop */}
      <div className="absolute inset-x-0 bottom-0 z-20 max-h-[70vh] overflow-y-auto rounded-t-2xl border-t border-border bg-card px-4 pb-5 pt-3 shadow-2xl sm:inset-auto sm:right-0 sm:top-0 sm:h-full sm:max-h-none sm:w-80 sm:rounded-none sm:rounded-l-xl sm:border-l sm:border-t-0 sm:pt-4">
        {/* Mobile drag indicator */}
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-border sm:hidden" />

        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">기사 상세</h3>
          <div className="flex items-center gap-1">
            {node.url && (
              <BookmarkButton
                articleId={node.id}
                title={node.title}
                publisher={node.publisher}
                url={node.url}
                size="sm"
              />
            )}
            <button
              onClick={onClose}
              className="rounded-md p-1.5 transition-colors hover:bg-secondary"
              aria-label="상세 패널 닫기"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>

        <div className="space-y-3">
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
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
            {node.publisher && (
              <div className="flex items-center gap-1.5">
                <Building2 className="h-3.5 w-3.5 shrink-0" />
                <span>{node.publisher}</span>
              </div>
            )}
            {node.published_at && (
              <div className="flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5 shrink-0" />
                <span>{formatDate(node.published_at)}</span>
              </div>
            )}
          </div>

          {/* Badges */}
          <div className="flex flex-wrap gap-1.5">
            {node.is_origin && (
              <Badge stage="origin">기원 기사</Badge>
            )}
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
          </div>

          {/* Similarity Score */}
          {!node.is_origin && (
            <div className="rounded-lg bg-secondary/50 p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Percent className="h-3.5 w-3.5" />
                  유사도
                </div>
                <span className="text-lg font-bold tabular-nums">
                  {(node.similarity_score * 100).toFixed(1)}
                  <span className="text-sm font-normal text-muted-foreground">%</span>
                </span>
              </div>
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full rounded-full bg-lifecycle-origin transition-all"
                  style={{ width: `${node.similarity_score * 100}%` }}
                />
              </div>
            </div>
          )}

          {/* Content Preview */}
          {isLoadingDetail && (
            <div className="rounded-lg border border-border bg-secondary/20 p-3">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                본문을 불러오는 중...
              </div>
            </div>
          )}

          {!isLoadingDetail && detailError && (
            <div className="rounded-lg border border-border bg-secondary/20 p-3">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <AlertCircle className="h-4 w-4" />
                {detailError}
              </div>
            </div>
          )}

          {!isLoadingDetail && !detailError && contentPreview && (
            <div className="rounded-lg border border-border bg-secondary/20 p-3">
              <p className="mb-1 text-xs font-medium text-muted-foreground">본문 미리보기</p>
              <p className="text-xs leading-relaxed text-foreground/80">{contentPreview}</p>
            </div>
          )}

          {!isLoadingDetail && !detailError && !contentPreview && articleDetail && (
            <div className="rounded-lg border border-border bg-secondary/20 p-3">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <AlertCircle className="h-4 w-4" />
                본문을 불러올 수 없습니다
              </div>
            </div>
          )}

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
    </>
  )
}
