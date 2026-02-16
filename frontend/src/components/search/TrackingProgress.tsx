import { Check, Loader2, Circle } from 'lucide-react'
import { useTrackingStore } from '@/stores/useTrackingStore'

const STAGES = [
  { key: 'crawling', label: '기사 수집', threshold: 20 },
  { key: 'embedding', label: '임베딩 생성', threshold: 40 },
  { key: 'similarity', label: '유사도 분석', threshold: 75 },
  { key: 'timeline', label: '타임라인 구성', threshold: 85 },
  { key: 'complete', label: '분석 완료', threshold: 100 },
] as const

export default function TrackingProgress() {
  const { trackingStatus, isPolling, searchError } = useTrackingStore()

  if (!trackingStatus || (!isPolling && trackingStatus.status !== 'completed' && trackingStatus.status !== 'error')) return null

  const { progress, total_articles, status } = trackingStatus

  return (
    <div className="mt-8 w-full max-w-lg space-y-5">
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
                  ? '분석 중...'
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
        {STAGES.map((stage) => {
          const isDone = progress >= stage.threshold
          const isActive =
            !isDone &&
            progress >= (STAGES[STAGES.indexOf(stage) - 1]?.threshold ?? 0)

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
