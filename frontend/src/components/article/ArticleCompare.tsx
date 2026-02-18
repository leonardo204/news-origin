/**
 * ArticleCompare - 기사 나란히 비교 모달
 * v1.0.0 - 타임라인 기사 목록에서 원본 기사와 관련 기사를 비교
 */
import { X, ArrowLeftRight, ExternalLink, Newspaper, Clock } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { formatRelativeTime, LIFECYCLE_LABELS } from '@/lib/utils'
import type { TimelineItem, LifecycleStage, SimilarityCategory } from '@/types'

interface ArticleCompareProps {
  item1: TimelineItem
  item2: TimelineItem
  onClose: () => void
}

function getSimilarityCategory(score: number): SimilarityCategory {
  if (score >= 0.9) return 'same'
  if (score >= 0.7) return 'derivative'
  return 'related'
}

const SIMILARITY_LABELS: Record<SimilarityCategory, string> = {
  same: '동일',
  derivative: '파생',
  related: '관련',
}

const SIMILARITY_COLORS: Record<SimilarityCategory, string> = {
  same: 'text-green-400',
  derivative: 'text-yellow-400',
  related: 'text-orange-400',
}

export default function ArticleCompare({ item1, item2, onClose }: ArticleCompareProps) {
  // Extract title words for keyword matching (2+ chars, Korean/alphanumeric)
  function extractWords(title: string): Set<string> {
    return new Set(title.split(/[\s,·「」『』【】\[\]()（）]+/).filter((w) => w.length >= 2))
  }

  const words1 = extractWords(item1.title)
  const words2 = extractWords(item2.title)
  const commonWords = [...words1].filter((w) => words2.has(w))

  const similarity = item2.is_origin ? item1.similarity_score : item2.similarity_score
  const category = getSimilarityCategory(similarity)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl rounded-xl border border-border bg-background shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <ArrowLeftRight className="h-4 w-4 text-lifecycle-spread" />
            기사 비교
          </h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted-foreground hover:bg-secondary"
            aria-label="닫기"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Similarity bar */}
        <div className="flex items-center justify-center gap-3 border-b border-border bg-secondary/30 px-6 py-3">
          <span className="text-xs text-muted-foreground">유사도</span>
          <span className={`text-2xl font-bold tabular-nums ${SIMILARITY_COLORS[category]}`}>
            {Math.round(similarity * 100)}%
          </span>
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              category === 'same'
                ? 'bg-green-400/15 text-green-400'
                : category === 'derivative'
                  ? 'bg-yellow-400/15 text-yellow-400'
                  : 'bg-orange-400/15 text-orange-400'
            }`}
          >
            {SIMILARITY_LABELS[category]}
          </span>
          {/* Visual similarity bar */}
          <div className="flex h-2 w-24 overflow-hidden rounded-full bg-secondary">
            <div
              className={`h-full rounded-full transition-all ${
                category === 'same'
                  ? 'bg-green-400'
                  : category === 'derivative'
                    ? 'bg-yellow-400'
                    : 'bg-orange-400'
              }`}
              style={{ width: `${Math.round(similarity * 100)}%` }}
            />
          </div>
        </div>

        {/* Side-by-side articles */}
        <div className="grid grid-cols-2 divide-x divide-border">
          {[item1, item2].map((item) => (
            <div key={item.article_id} className="p-5 space-y-3">
              {/* Origin/user badge */}
              <div className="flex items-center gap-1.5 flex-wrap">
                {item.is_origin && (
                  <span className="rounded-full bg-lifecycle-origin/15 px-2 py-0.5 text-[10px] font-medium text-lifecycle-origin">
                    ★ 기원
                  </span>
                )}
                {item.is_user_selected && !item.is_origin && (
                  <span className="rounded-full bg-blue-500/15 px-2 py-0.5 text-[10px] font-medium text-blue-500">
                    ◎ 선택한 기사
                  </span>
                )}
                {item.lifecycle_stage && (
                  <Badge stage={item.lifecycle_stage as LifecycleStage}>
                    {LIFECYCLE_LABELS[item.lifecycle_stage as LifecycleStage]}
                  </Badge>
                )}
              </div>

              {/* Title */}
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-semibold leading-snug">
                  {highlightCommon(item.title, commonWords)}
                </h3>
                {item.url && (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 text-muted-foreground hover:text-foreground"
                    aria-label="원문 보기"
                  >
                    <ExternalLink className="h-4 w-4" />
                  </a>
                )}
              </div>

              {/* Meta */}
              <div className="space-y-1.5 text-xs text-muted-foreground">
                {item.publisher && (
                  <div className="flex items-center gap-1.5">
                    <Newspaper className="h-3 w-3 shrink-0" />
                    <span className="truncate">{item.publisher}</span>
                  </div>
                )}
                {item.published_at && (
                  <div className="flex items-center gap-1.5">
                    <Clock className="h-3 w-3 shrink-0" />
                    {formatRelativeTime(item.published_at)}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Common keywords footer */}
        {commonWords.length > 0 && (
          <div className="border-t border-border px-6 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">공통 키워드:</span>
              {commonWords.slice(0, 10).map((word) => (
                <span
                  key={word}
                  className="rounded-full bg-lifecycle-origin/15 px-2 py-0.5 text-xs font-medium text-lifecycle-origin"
                >
                  {word}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/** Wrap common words in the title with a highlight span */
function highlightCommon(title: string, commonWords: string[]): React.ReactNode {
  if (commonWords.length === 0) return title

  // Build a regex that matches any common word
  const pattern = new RegExp(
    `(${commonWords.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`,
    'g',
  )
  const parts = title.split(pattern)
  const wordSet = new Set(commonWords)

  return parts.map((part, i) =>
    wordSet.has(part) ? (
      <mark
        key={i}
        className="rounded bg-lifecycle-origin/20 px-0.5 text-lifecycle-origin not-italic"
      >
        {part}
      </mark>
    ) : (
      part
    ),
  )
}
