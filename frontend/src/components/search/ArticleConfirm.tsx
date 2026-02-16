import { ExternalLink, Clock, Building2, CheckCircle2, Loader2 } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { useTrackingStore } from '@/stores/useTrackingStore'
import { formatDate, truncate } from '@/lib/utils'
import type { Article, TrackCandidate } from '@/types'

export default function ArticleConfirm() {
  const { searchResult, confirmArticle, selectCandidate, isSearching, selectedCandidateUrl, trackingStatus } = useTrackingStore()

  if (!searchResult) return null

  // Direct URL input: article is already identified
  if (searchResult.article) {
    // 추적 시작 버튼: 실패 시 재시도용 또는 아직 추적 시작 전일 때만 표시
    const isFailed = trackingStatus?.status === 'failed' || trackingStatus?.status === 'error'
    const isTrackingActive = trackingStatus && !isFailed
    return (
      <ConfirmSingleArticle
        article={searchResult.article}
        onConfirm={() => confirmArticle(searchResult.article!.id)}
        showConfirmButton={!isTrackingActive}
        isFailed={!!isFailed}
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
        selectedUrl={selectedCandidateUrl}
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
  showConfirmButton,
  isFailed,
}: {
  article: Article
  onConfirm: () => void
  showConfirmButton: boolean
  isFailed: boolean
}) {
  return (
    <Card className="mt-6 max-w-2xl">
      <CardContent className="p-3 sm:p-4">
        <div className="space-y-3">
          <div className="space-y-2">
            <h3 className="text-sm font-semibold leading-tight sm:text-base">{article.title}</h3>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground sm:gap-3">
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
          {showConfirmButton && (
            <Button onClick={onConfirm} className="w-full sm:w-auto" variant={isFailed ? 'destructive' : 'default'}>
              <CheckCircle2 className="mr-1.5 h-4 w-4" />
              {isFailed ? '다시 시도' : '추적 시작'}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function CandidateList({
  candidates,
  onSelect,
  disabled,
  selectedUrl,
}: {
  candidates: TrackCandidate[]
  onSelect: (candidate: { url: string; title?: string; publisher?: string; published_at?: string }) => Promise<void>
  disabled: boolean
  selectedUrl: string | null
}) {
  return (
    <div className="mt-6 max-w-2xl space-y-3">
      <h3 className="text-sm font-medium text-muted-foreground">
        {candidates.length}개의 관련 기사를 찾았습니다. 추적할 기사를 선택하세요:
      </h3>
      {candidates.map((candidate, i) => {
        const isSelected = selectedUrl === candidate.url
        return (
          <Card
            key={i}
            className={`transition-colors ${
              isSelected
                ? 'border-lifecycle-origin/50 opacity-80'
                : disabled
                  ? 'opacity-50'
                  : 'cursor-pointer hover:border-lifecycle-origin/50'
            }`}
            onClick={() => {
              if (!disabled) {
                onSelect({
                  url: candidate.url,
                  title: candidate.title,
                  publisher: candidate.publisher ?? undefined,
                  published_at: candidate.published_at ? String(candidate.published_at) : undefined,
                })
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
                {isSelected ? (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-lifecycle-origin" />
                ) : (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-muted-foreground" />
                )}
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
