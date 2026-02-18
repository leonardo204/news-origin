import { useState } from 'react'
import { X, ArrowLeftRight, ExternalLink, Newspaper, Clock } from 'lucide-react'
import { formatRelativeTime } from '@/lib/utils'
import type { ClusterArticle } from '@/types'

interface ArticleCompareProps {
  articles: ClusterArticle[]
  onClose: () => void
}

export default function ArticleCompare({ articles, onClose }: ArticleCompareProps) {
  const [leftIdx, setLeftIdx] = useState(0)
  const [rightIdx, setRightIdx] = useState(Math.min(1, articles.length - 1))

  if (articles.length < 2) return null

  const left = articles[leftIdx]
  const right = articles[rightIdx]

  // Extract keywords from titles for highlighting
  const leftWords = new Set(left.title.split(/\s+/).filter((w) => w.length > 1))
  const rightWords = new Set(right.title.split(/\s+/).filter((w) => w.length > 1))
  const commonWords = [...leftWords].filter((w) => rightWords.has(w))

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-4xl rounded-xl border border-border bg-background shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <ArrowLeftRight className="h-5 w-5 text-lifecycle-spread" />
            기사 비교
          </h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted-foreground hover:bg-secondary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Article Selectors */}
        <div className="grid grid-cols-2 gap-4 border-b border-border px-6 py-3">
          <select
            value={leftIdx}
            onChange={(e) => setLeftIdx(Number(e.target.value))}
            className="rounded-lg border border-border bg-secondary/50 px-3 py-2 text-sm"
          >
            {articles.map((a, i) => (
              <option key={a.id} value={i} disabled={i === rightIdx}>
                {a.publisher ? `[${a.publisher}] ` : ''}
                {a.title.slice(0, 50)}
              </option>
            ))}
          </select>
          <select
            value={rightIdx}
            onChange={(e) => setRightIdx(Number(e.target.value))}
            className="rounded-lg border border-border bg-secondary/50 px-3 py-2 text-sm"
          >
            {articles.map((a, i) => (
              <option key={a.id} value={i} disabled={i === leftIdx}>
                {a.publisher ? `[${a.publisher}] ` : ''}
                {a.title.slice(0, 50)}
              </option>
            ))}
          </select>
        </div>

        {/* Comparison Content */}
        <div className="grid grid-cols-2 gap-4 p-6">
          {[left, right].map((article) => (
            <div key={article.id} className="space-y-3 rounded-lg border border-border/50 p-4">
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-semibold leading-snug">{article.title}</h3>
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 text-muted-foreground hover:text-foreground"
                >
                  <ExternalLink className="h-4 w-4" />
                </a>
              </div>
              <div className="space-y-1.5 text-xs text-muted-foreground">
                {article.publisher && (
                  <div className="flex items-center gap-1.5">
                    <Newspaper className="h-3 w-3" />
                    {article.publisher}
                  </div>
                )}
                {article.published_at && (
                  <div className="flex items-center gap-1.5">
                    <Clock className="h-3 w-3" />
                    {formatRelativeTime(article.published_at)}
                  </div>
                )}
                {article.similarity_score < 1 && (
                  <div className="flex items-center gap-1.5">
                    <span className="font-medium">유사도:</span>
                    <span
                      className={`font-medium ${
                        article.similarity_score >= 0.9
                          ? 'text-green-400'
                          : article.similarity_score >= 0.7
                            ? 'text-yellow-400'
                            : 'text-orange-400'
                      }`}
                    >
                      {Math.round(article.similarity_score * 100)}%
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Common Keywords */}
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
