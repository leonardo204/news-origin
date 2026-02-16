import { Check, Loader2, Circle } from 'lucide-react'
import { useTrackingStore } from '@/stores/useTrackingStore'

const INSTANT_STAGES = [
  { key: 'embedding', label: '임베딩 생성', threshold: 20 },
  { key: 'search', label: '유사 기사 검색', threshold: 40 },
  { key: 'matching', label: '기사 매칭', threshold: 60 },
  { key: 'timeline', label: '타임라인 구성', threshold: 80 },
  { key: 'complete', label: '분석 완료', threshold: 100 },
] as const

const LIVE_STAGES = [
  { key: 'crawling', label: '실시간 기사 수집', threshold: 20 },
  { key: 'embedding', label: '임베딩 생성', threshold: 40 },
  { key: 'similarity', label: '유사도 분석', threshold: 75 },
  { key: 'timeline', label: '타임라인 구성', threshold: 85 },
  { key: 'complete', label: '분석 완료', threshold: 100 },
] as const

export default function TrackingProgress() {
  const { trackingStatus, isPolling, searchError } = useTrackingStore()

  if (!trackingStatus || (!isPolling && trackingStatus.status !== 'completed' && trackingStatus.status !== 'error')) return null

  const { progress, total_articles, status, tracking_type } = trackingStatus
  const isLive = tracking_type === 'live'
  const stages: ReadonlyArray<{ readonly key: string; readonly label: string; readonly threshold: number }> =
    isLive ? LIVE_STAGES : INSTANT_STAGES

  return (
    <div className="mt-8 w-full max-w-lg space-y-5">
      {/* Tracking type indicator */}
      <div className="flex items-center justify-center gap-2">
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
          isLive
            ? 'bg-lifecycle-origin/15 text-lifecycle-origin'
            : 'bg-muted text-muted-foreground'
        }`}>
          {isLive ? 'Live 추적' : '즉시 분석'}
        </span>
      </div>

      {/* Progress bar */}
      <div className="space-y-2">
        <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
          <div
            className={`h-full rounded-full transition-all duration-700 ease-out ${
              status === 'error' || status === 'failed' ? 'bg-red-500' : 'bg-lifecycle-origin'
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {status === 'completed'
              ? '완료'
              : status === 'error' || status === 'failed'
                ? '오류 발생'
                : status === 'processing'
                  ? isLive ? 'Live 분석 중...' : '빠른 분석 중...'
                  : '대기 중...'}
          </span>
          <span>
            {total_articles > 0 && `${total_articles}개 기사 · `}
            {progress}%
          </span>
        </div>
      </div>

      {/* Stage breakdown */}
      <div className="space-y-1.5">
        {stages.map((stage) => {
          const isDone = progress >= stage.threshold
          const isActive =
            !isDone &&
            progress >= (stages[stages.indexOf(stage) - 1]?.threshold ?? 0)

          return (
            <div
              key={stage.key}
              className={`flex items-center gap-2.5 rounded-md px-3 py-1.5 text-sm transition-colors ${
                isDone
                  ? 'text-foreground'
                  : isActive
                    ? 'text-foreground'
                    : 'text-muted-foreground/50'
              }`}
            >
              {isDone ? (
                <Check className="h-3.5 w-3.5 shrink-0 text-lifecycle-origin" />
              ) : isActive ? (
                <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-lifecycle-origin" />
              ) : (
                <Circle className="h-3.5 w-3.5 shrink-0" />
              )}
              <span>{stage.label}</span>
            </div>
          )
        })}
      </div>

      {/* Error */}
      {searchError && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-400">
          {searchError}
        </div>
      )}
    </div>
  )
}
