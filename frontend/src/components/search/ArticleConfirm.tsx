import { ExternalLink, Clock, Building2, CheckCircle2, Loader2 } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { useTrackingStore } from '@/stores/useTrackingStore'
import { formatDate, truncate } from '@/lib/utils'
import type { Article, TrackCandidate } from '@/types'

export default function ArticleConfirm() {
  const { searchResult, confirmArticle, selectCandidate, isSearching } = useTrackingStore()

  if (!searchResult) return null

  // Direct URL input: article is already identified
  if (searchResult.article) {
    return (
      <ConfirmSingleArticle
        article={searchResult.article}
        onConfirm={() => confirmArticle(searchResult.article!.id)}
      />
    )
  }

  // Title search: show candidates
  if (searchResult.candidates.length > 0) {
    return (
      <CandidateList
        candidates={searchResult.candidates}
        onSelect={selectCandidate}
        disabled={isSearching}
      />
    )
  }

  return (
    <div className="mt-6 text-center text-muted-foreground">
      <p>검색 결과가 없습니다. 다른 검색어를 시도해보세요.</p>
    </div>
  )
}

function ConfirmSingleArticle({
  article,
  onConfirm,
}: {
  article: Article
  onConfirm: () => void
}) {
  return (
    <Card className="mt-6 max-w-2xl">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 space-y-2">
            <h3 className="font-semibold leading-tight">{article.title}</h3>
            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              {article.publisher && (
                <span className="flex items-center gap-1">
                  <Building2 className="h-3 w-3" />
                  {article.publisher}
                </span>
              )}
              {article.published_at && (
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {formatDate(article.published_at)}
                </span>
              )}
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-lifecycle-origin hover:underline"
              >
                <ExternalLink className="h-3 w-3" />
                원문
              </a>
            </div>
            {article.summary && (
              <p className="text-sm text-muted-foreground">
                {truncate(article.summary, 200)}
              </p>
            )}
          </div>
          <Button onClick={onConfirm} className="shrink-0">
            <CheckCircle2 className="mr-1.5 h-4 w-4" />
            추적 시작
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function CandidateList({
  candidates,
  onSelect,
  disabled,
}: {
  candidates: TrackCandidate[]
  onSelect: (url: string) => Promise<void>
  disabled: boolean
}) {
  return (
    <div className="mt-6 max-w-2xl space-y-3">
      <h3 className="text-sm font-medium text-muted-foreground">
        {candidates.length}개의 관련 기사를 찾았습니다. 추적할 기사를 선택하세요:
      </h3>
      {candidates.map((candidate, i) => (
        <Card
          key={i}
          className={`transition-colors ${disabled ? 'opacity-50' : 'cursor-pointer hover:border-lifecycle-origin/50'}`}
          onClick={() => {
            if (!disabled) {
              onSelect(candidate.url)
            }
          }}
        >
          <CardContent className="p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 space-y-1">
                <h4 className="text-sm font-medium leading-tight">
                  {candidate.title}
                </h4>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  {candidate.publisher && (
                    <span className="flex items-center gap-1">
                      <Building2 className="h-3 w-3" />
                      {candidate.publisher}
                    </span>
                  )}
                  {candidate.published_at && (
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatDate(candidate.published_at)}
                    </span>
                  )}
                </div>
              </div>
              {disabled ? (
                <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
              ) : (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-muted-foreground" />
              )}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
