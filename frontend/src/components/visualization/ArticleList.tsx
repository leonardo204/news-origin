import { useState, useMemo } from 'react'
import { ArrowUp, ArrowDown, Filter, X, ExternalLink, ArrowLeftRight } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import BookmarkButton from '@/components/ui/BookmarkButton'
import ArticleCompare from '@/components/article/ArticleCompare'
import { LIFECYCLE_LABELS } from '@/lib/utils'
import type { TimelineItem, LifecycleStage } from '@/types'

type SortField = 'title' | 'publisher' | 'lifecycle_stage' | 'similarity_score' | 'published_at'
type SortDir = 'asc' | 'desc'

const ALL_STAGES: LifecycleStage[] = [
  'origin', 'spread', 'explosion', 'sustained', 'fadeout', 'resurge',
]

interface ArticleListProps {
  items: TimelineItem[]
}

export default function ArticleList({ items }: ArticleListProps) {
  const [activeStages, setActiveStages] = useState<Set<LifecycleStage>>(new Set())
  const [sortField, setSortField] = useState<SortField>('published_at')
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [showFilter, setShowFilter] = useState(false)
  const [compareItem, setCompareItem] = useState<TimelineItem | null>(null)

  const originItem = useMemo(() => items.find((i) => i.is_origin) ?? null, [items])

  const hasFilter = activeStages.size > 0

  const filtered = useMemo(() => {
    let result = items
    if (activeStages.size > 0) {
      result = result.filter((item) => activeStages.has(item.lifecycle_stage as LifecycleStage))
    }

    result = [...result].sort((a, b) => {
      // 기원 기사는 항상 맨 위에 위치
      if (a.is_origin && !b.is_origin) return -1
      if (!a.is_origin && b.is_origin) return 1

      let cmp = 0
      switch (sortField) {
        case 'title':
          cmp = a.title.localeCompare(b.title, 'ko')
          break
        case 'publisher':
          cmp = (a.publisher || '').localeCompare(b.publisher || '', 'ko')
          break
        case 'lifecycle_stage':
          cmp = (a.lifecycle_stage || '').localeCompare(b.lifecycle_stage || '')
          break
        case 'similarity_score':
          cmp = a.similarity_score - b.similarity_score
          break
        case 'published_at':
          cmp = new Date(a.published_at).getTime() - new Date(b.published_at).getTime()
          break
      }
      return sortDir === 'asc' ? cmp : -cmp
    })

    return result
  }, [items, activeStages, sortField, sortDir])

  function toggleStage(stage: LifecycleStage) {
    setActiveStages((prev) => {
      const next = new Set(prev)
      if (next.has(stage)) {
        next.delete(stage)
      } else {
        next.add(stage)
      }
      return next
    })
  }

  function handleSort(field: SortField) {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDir(field === 'similarity_score' ? 'desc' : 'asc')
    }
  }

  function resetFilter() {
    setActiveStages(new Set())
  }

  function SortIcon({ field }: { field: SortField }) {
    if (sortField !== field) return null
    return sortDir === 'asc' ? (
      <ArrowUp className="ml-0.5 inline h-3 w-3" />
    ) : (
      <ArrowDown className="ml-0.5 inline h-3 w-3" />
    )
  }

  if (items.length === 0) return null

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>
          기사 목록{' '}
          <span className="font-normal text-muted-foreground">
            {hasFilter ? `${filtered.length}건 / 전체 ${items.length}건` : `${items.length}건`}
          </span>
        </CardTitle>
        <div className="flex items-center gap-1.5">
          {hasFilter && (
            <Button variant="ghost" size="sm" onClick={resetFilter} className="h-7 gap-1 px-2 text-xs">
              <X className="h-3 w-3" />
              초기화
            </Button>
          )}
          <Button
            variant={showFilter ? 'secondary' : 'ghost'}
            size="sm"
            onClick={() => setShowFilter(!showFilter)}
            className="h-7 gap-1 px-2 text-xs"
          >
            <Filter className="h-3 w-3" />
            필터
          </Button>
        </div>
      </CardHeader>

      {showFilter && (
        <div className="border-t border-border px-4 py-3">
          <p className="mb-2 text-xs text-muted-foreground">단계별 필터</p>
          <div className="flex flex-wrap gap-1.5">
            {ALL_STAGES.map((stage) => (
              <button
                key={stage}
                onClick={() => toggleStage(stage)}
                className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                  activeStages.has(stage)
                    ? 'border-foreground/30 bg-foreground/10 text-foreground'
                    : 'border-border text-muted-foreground hover:border-foreground/20'
                }`}
              >
                {LIFECYCLE_LABELS[stage]}
              </button>
            ))}
          </div>
        </div>
      )}

      <CardContent>
        {/* Desktop: table layout */}
        <div className="hidden sm:block">
          <div className="space-y-1">
            {/* Sortable header */}
            <div className="grid grid-cols-[1fr_100px_80px_80px_32px_32px] gap-2 px-2 pb-2 text-xs font-medium text-muted-foreground">
              <button className="text-left hover:text-foreground" onClick={() => handleSort('title')}>
                제목<SortIcon field="title" />
              </button>
              <button className="text-left hover:text-foreground" onClick={() => handleSort('publisher')}>
                언론사<SortIcon field="publisher" />
              </button>
              <button className="text-left hover:text-foreground" onClick={() => handleSort('lifecycle_stage')}>
                단계<SortIcon field="lifecycle_stage" />
              </button>
              <button className="text-right hover:text-foreground" onClick={() => handleSort('similarity_score')}>
                유사도<SortIcon field="similarity_score" />
              </button>
              <span></span>
              <span></span>
            </div>

            {filtered.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                필터 조건에 맞는 기사가 없습니다.
              </p>
            ) : (
              filtered.map((item) => (
                <div
                  key={item.article_id}
                  className="grid grid-cols-[1fr_100px_80px_80px_32px_32px] items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors hover:bg-secondary/30"
                >
                  <div className="overflow-hidden">
                    <a
                      href={item.url || undefined}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`flex items-center gap-2 ${
                        item.url ? 'cursor-pointer' : 'cursor-default'
                      }`}
                      onClick={item.url ? undefined : (e) => e.preventDefault()}
                    >
                      {item.is_origin && <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center text-[10px] leading-none" title="기원 기사">★</span>}
                      {item.is_user_selected && !item.is_origin && <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center text-[10px] leading-none text-blue-500" title="내가 선택한 기사">◎</span>}
                      <span className="truncate">{item.title}</span>
                      {item.url && <ExternalLink className="h-3 w-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 [a:hover_&]:opacity-100" />}
                    </a>
                    {item.summary && (
                      <p className="mt-0.5 truncate text-xs text-muted-foreground/60">{item.summary}</p>
                    )}
                  </div>
                  <span className="truncate text-xs text-muted-foreground">
                    {item.publisher || '-'}
                  </span>
                  <div>
                    {item.lifecycle_stage && (
                      <Badge stage={item.lifecycle_stage as LifecycleStage}>
                        {LIFECYCLE_LABELS[item.lifecycle_stage as LifecycleStage]}
                      </Badge>
                    )}
                  </div>
                  <span className="text-right text-xs tabular-nums text-muted-foreground">
                    {(item.similarity_score * 100).toFixed(1)}%
                  </span>
                  {item.url && (
                    <BookmarkButton
                      articleId={item.article_id}
                      title={item.title}
                      publisher={item.publisher}
                      url={item.url}
                      size="sm"
                      className="justify-self-center"
                    />
                  )}
                  {!item.is_origin && originItem ? (
                    <button
                      onClick={() => setCompareItem(item)}
                      className="justify-self-center rounded p-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
                      title="기원 기사와 비교"
                      aria-label="비교"
                    >
                      <ArrowLeftRight className="h-3.5 w-3.5" />
                    </button>
                  ) : (
                    <span />
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Mobile: card layout */}
        <div className="sm:hidden">
          {/* Sort controls */}
          <div className="mb-2 flex flex-wrap gap-1.5 text-xs text-muted-foreground">
            {([['published_at', '시간'], ['similarity_score', '유사도'], ['title', '제목']] as const).map(([field, label]) => (
              <button
                key={field}
                onClick={() => handleSort(field)}
                className={`rounded-md px-2 py-1 transition-colors ${sortField === field ? 'bg-secondary text-foreground' : 'hover:text-foreground'}`}
              >
                {label}<SortIcon field={field} />
              </button>
            ))}
          </div>

          {filtered.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              필터 조건에 맞는 기사가 없습니다.
            </p>
          ) : (
            <div className="space-y-2">
              {filtered.map((item) => (
                <div
                  key={item.article_id}
                  className="relative rounded-lg border border-border/50 p-3 transition-colors hover:bg-secondary/30"
                >
                  <a
                    href={item.url || undefined}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`block ${
                      item.url ? 'cursor-pointer' : 'cursor-default'
                    }`}
                    onClick={item.url ? undefined : (e) => e.preventDefault()}
                  >
                    <p className="flex items-start gap-1 pr-8 text-sm font-medium leading-snug">
                      {item.is_origin && <span className="mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center text-[10px] leading-none" title="기원 기사">★</span>}
                      {item.is_user_selected && !item.is_origin && <span className="mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center text-[10px] leading-none text-blue-500" title="내가 선택한 기사">◎</span>}
                      <span>{item.title}</span>
                    </p>
                    {item.summary && (
                      <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground/60">{item.summary}</p>
                    )}
                    <div className="mt-1.5 flex flex-wrap items-center gap-2">
                      {item.publisher && (
                        <span className="text-xs text-muted-foreground">{item.publisher}</span>
                      )}
                      {item.lifecycle_stage && (
                        <Badge stage={item.lifecycle_stage as LifecycleStage}>
                          {LIFECYCLE_LABELS[item.lifecycle_stage as LifecycleStage]}
                        </Badge>
                      )}
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {(item.similarity_score * 100).toFixed(1)}%
                      </span>
                      {item.url && <ExternalLink className="h-3 w-3 text-muted-foreground/50" />}
                    </div>
                  </a>
                  <div className="absolute right-2 top-2 flex items-center gap-1">
                    {!item.is_origin && originItem && (
                      <button
                        onClick={() => setCompareItem(item)}
                        className="rounded p-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
                        title="기원 기사와 비교"
                        aria-label="비교"
                      >
                        <ArrowLeftRight className="h-3.5 w-3.5" />
                      </button>
                    )}
                    {item.url && (
                      <BookmarkButton
                        articleId={item.article_id}
                        title={item.title}
                        publisher={item.publisher}
                        url={item.url}
                        size="sm"
                      />
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>

      {/* Compare modal */}
      {compareItem && originItem && (
        <ArticleCompare
          item1={originItem}
          item2={compareItem}
          onClose={() => setCompareItem(null)}
        />
      )}
    </Card>
  )
}
