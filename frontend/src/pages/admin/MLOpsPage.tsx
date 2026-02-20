import { useState, useEffect } from 'react'
import {
  Brain,
  Database,
  FlaskConical,
  Settings2,
  RefreshCw,
  CheckCircle2,
  Clock,
  Archive,
  Loader2,
  Calendar,
  ArrowRight,
  CircleDot,
  Target,
  Rocket,
  RotateCcw,
  Search,
  TrendingUp,
  Activity,
  Zap,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { fetchMLOps } from '@/services/adminApi'

interface ModelVersion {
  version: string
  base_model: string
  f1: number
  precision: number
  recall: number
  status: string
  samples: number
  created_at: string
}

interface PipelineStage {
  id: string
  label: string
  status: string
  progress?: number
  target?: number
  detail: string
}

interface RecentEvaluation {
  title: string
  quality_score: number
  method: string
  created_at: string
}

interface Predictions {
  finetune_ready: boolean
  daily_collection_rate: number
  est_days_to_ready: number | null
  est_ready_date_kst: string | null
  next_finetune_trigger: string
  current_phase: string
  timestamp_kst: string
}

interface MLOpsData {
  current_model: {
    version: string
    base_model: string
    f1: number | null
    is_active: boolean
  } | null
  training_data: {
    total: number
    unused: number
    avg_quality: number
  }
  model_versions: ModelVersion[]
  config: {
    min_quality: number
    min_samples: number
    eval_sample_size: number
  }
  schedule?: Array<{
    task: string
    interval: string
    detail: string
    next_run_kst?: string
  }>
  pipeline?: {
    stages: PipelineStage[]
    summary: {
      total_samples: number
      unused_samples: number
      target_samples: number
      readiness_percent: number
      active_model: string
    }
  }
  recent_evaluations?: RecentEvaluation[]
  predictions?: Predictions
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-28 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800"
          />
        ))}
      </div>
      <div className="h-64 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" />
    </div>
  )
}

function getStatusBadge(status: string) {
  switch (status) {
    case 'active':
      return {
        bg: 'bg-emerald-100 dark:bg-emerald-900/30',
        text: 'text-emerald-700 dark:text-emerald-400',
        label: '활성',
        Icon: CheckCircle2,
      }
    case 'ready':
      return {
        bg: 'bg-blue-100 dark:bg-blue-900/30',
        text: 'text-blue-700 dark:text-blue-400',
        label: '준비됨',
        Icon: Clock,
      }
    case 'training':
      return {
        bg: 'bg-yellow-100 dark:bg-yellow-900/30',
        text: 'text-yellow-700 dark:text-yellow-400',
        label: '학습 중',
        Icon: Loader2,
      }
    case 'retired':
      return {
        bg: 'bg-gray-100 dark:bg-gray-800',
        text: 'text-gray-600 dark:text-gray-400',
        label: '폐기됨',
        Icon: Archive,
      }
    default:
      return {
        bg: 'bg-gray-100 dark:bg-gray-800',
        text: 'text-gray-600 dark:text-gray-400',
        label: status,
        Icon: Clock,
      }
  }
}

function formatF1(value: number | null | undefined): string {
  if (value == null) return '-'
  return (value * 100).toFixed(1) + '%'
}

const STAGE_ICONS: Record<string, typeof Database> = {
  collect: Database,
  evaluate: Search,
  readiness: Target,
  finetune: FlaskConical,
  deploy: Rocket,
  reextract: RotateCcw,
}

function getStageStyle(status: string) {
  switch (status) {
    case 'active':
      return { ring: 'ring-blue-400', bg: 'bg-blue-50 dark:bg-blue-900/30', text: 'text-blue-600 dark:text-blue-400', badge: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300', badgeLabel: '진행 중' }
    case 'done':
      return { ring: 'ring-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-900/30', text: 'text-emerald-600 dark:text-emerald-400', badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300', badgeLabel: '완료' }
    case 'ready':
      return { ring: 'ring-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-900/30', text: 'text-emerald-600 dark:text-emerald-400', badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300', badgeLabel: '준비됨' }
    case 'collecting':
      return { ring: 'ring-amber-400', bg: 'bg-amber-50 dark:bg-amber-900/30', text: 'text-amber-600 dark:text-amber-400', badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300', badgeLabel: '수집 중' }
    default:
      return { ring: 'ring-gray-300 dark:ring-gray-600', bg: 'bg-gray-50 dark:bg-gray-800', text: 'text-gray-400 dark:text-gray-500', badge: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400', badgeLabel: '대기' }
  }
}

function formatTimeAgo(isoStr: string): string {
  const diff = Date.now() - new Date(isoStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '방금'
  if (mins < 60) return `${mins}분 전`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}시간 전`
  return `${Math.floor(hours / 24)}일 전`
}

export default function MLOpsPage() {
  const [data, setData] = useState<MLOpsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const { data: res } = await fetchMLOps()
      setData(res)
      setError(null)
    } catch (err) {
      console.error('MLOps fetch error:', err)
      setError('MLOps 데이터를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          MLOps 모니터링
        </h2>
        <LoadingSkeleton />
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          MLOps 모니터링
        </h2>
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-gray-500 dark:text-gray-400">{error}</p>
            <button
              onClick={loadData}
              className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
            >
              <RefreshCw className="h-4 w-4" />
              다시 시도
            </button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!data) return null

  const trainingStats = [
    {
      label: '학습 데이터 총계',
      value: data.training_data.total.toLocaleString('ko-KR'),
      suffix: '건',
      icon: Database,
      iconColor: 'text-blue-500',
      iconBg: 'bg-blue-50 dark:bg-blue-900/20',
    },
    {
      label: '미사용 데이터',
      value: data.training_data.unused.toLocaleString('ko-KR'),
      suffix: '건',
      icon: FlaskConical,
      iconColor: 'text-amber-500',
      iconBg: 'bg-amber-50 dark:bg-amber-900/20',
    },
    {
      label: '평균 품질 점수',
      value: data.training_data.avg_quality.toFixed(2),
      icon: CheckCircle2,
      iconColor: 'text-emerald-500',
      iconBg: 'bg-emerald-50 dark:bg-emerald-900/20',
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          MLOps 모니터링
        </h2>
        <div className="flex items-center gap-3">
          {data.predictions && (
            <span className="text-xs text-gray-400">
              {data.predictions.timestamp_kst}
            </span>
          )}
          <button
            onClick={loadData}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            새로고침
          </button>
        </div>
      </div>

      {/* Predictions Banner */}
      {data.predictions && (
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-indigo-500" />
                <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                  현재 상태
                </span>
                <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  data.predictions.finetune_ready
                    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                    : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                }`}>
                  {data.predictions.current_phase}
                </span>
              </div>
              <div className="h-4 w-px bg-gray-200 dark:bg-gray-700" />
              <div className="text-sm text-gray-500 dark:text-gray-400">
                <span className="font-medium text-gray-700 dark:text-gray-300">일일 수집률:</span>{' '}
                {data.predictions.daily_collection_rate}건/일
              </div>
              {data.predictions.est_days_to_ready != null && data.predictions.est_days_to_ready > 0 && (
                <>
                  <div className="h-4 w-px bg-gray-200 dark:bg-gray-700" />
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    <span className="font-medium text-gray-700 dark:text-gray-300">예상 준비 완료:</span>{' '}
                    ~{data.predictions.est_days_to_ready}일 후
                    {data.predictions.est_ready_date_kst && (
                      <span className="ml-1 text-xs text-gray-400">
                        ({data.predictions.est_ready_date_kst})
                      </span>
                    )}
                  </div>
                </>
              )}
              {data.predictions.finetune_ready && (
                <>
                  <div className="h-4 w-px bg-gray-200 dark:bg-gray-700" />
                  <div className="text-sm">
                    <span className="font-medium text-emerald-600 dark:text-emerald-400">
                      {data.predictions.next_finetune_trigger}
                    </span>
                  </div>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Current Model */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-purple-500" />
            현재 모델
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.current_model ? (
            <div className="flex flex-wrap items-center gap-6">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">버전</p>
                <p className="mt-0.5 text-lg font-bold text-gray-900 dark:text-gray-100">
                  {data.current_model.version}
                </p>
              </div>
              <div className="h-10 w-px bg-gray-200 dark:bg-gray-700" />
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  기반 모델
                </p>
                <p className="mt-0.5 text-sm font-medium text-gray-900 dark:text-gray-100">
                  {data.current_model.base_model}
                </p>
              </div>
              <div className="h-10 w-px bg-gray-200 dark:bg-gray-700" />
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  F1 Score
                </p>
                <p className="mt-0.5 text-lg font-bold text-blue-600 dark:text-blue-400">
                  {formatF1(data.current_model.f1)}
                </p>
              </div>
              <div className="h-10 w-px bg-gray-200 dark:bg-gray-700" />
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">상태</p>
                <span
                  className={`mt-0.5 inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    data.current_model.is_active
                      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                      : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
                  }`}
                >
                  {data.current_model.is_active ? '활성' : '비활성'}
                </span>
              </div>
            </div>
          ) : (
            <p className="py-4 text-center text-sm text-gray-400">
              활성 모델이 없습니다
            </p>
          )}
        </CardContent>
      </Card>

      {/* Pipeline Visualization */}
      {data.pipeline && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CircleDot className="h-5 w-5 text-blue-500" />
              MLOps 파이프라인
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Horizontal flow (desktop) / Vertical (mobile) */}
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:gap-0">
              {data.pipeline.stages.map((stage, idx) => {
                const style = getStageStyle(stage.status)
                const StageIcon = STAGE_ICONS[stage.id] || CircleDot
                const hasProgress = stage.progress != null && stage.target != null && stage.target > 0
                const progressPct = hasProgress ? Math.min(100, Math.round((stage.progress! / stage.target!) * 100)) : 0

                return (
                  <div key={stage.id} className="flex items-start gap-0 md:flex-1">
                    <div className="flex flex-1 flex-col items-center text-center">
                      {/* Icon circle */}
                      <div className={`flex h-12 w-12 items-center justify-center rounded-full ring-2 ${style.ring} ${style.bg}`}>
                        <StageIcon className={`h-5 w-5 ${style.text}`} />
                      </div>
                      {/* Label */}
                      <p className="mt-2 text-xs font-semibold text-gray-700 dark:text-gray-300">
                        {stage.label}
                      </p>
                      {/* Badge */}
                      <span className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${style.badge}`}>
                        {style.badgeLabel}
                      </span>
                      {/* Progress bar for collect/readiness */}
                      {hasProgress && (
                        <div className="mt-1.5 h-1.5 w-16 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                          <div
                            className="h-full rounded-full bg-blue-500 transition-all duration-500"
                            style={{ width: `${progressPct}%` }}
                          />
                        </div>
                      )}
                      {/* Detail */}
                      <p className="mt-1 text-[10px] text-gray-400">
                        {stage.detail}
                      </p>
                    </div>
                    {/* Arrow connector */}
                    {idx < data.pipeline!.stages.length - 1 && (
                      <div className="hidden shrink-0 pt-4 md:flex md:items-center md:px-1">
                        <ArrowRight className="h-4 w-4 text-gray-300 dark:text-gray-600" />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            {/* Summary bar */}
            <div className="mt-6 rounded-lg border border-gray-100 p-3 dark:border-gray-800">
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">학습 데이터 진행률</span>
                <span className="font-semibold text-gray-900 dark:text-gray-100">
                  {data.pipeline.summary.unused_samples} / {data.pipeline.summary.target_samples}건
                  <span className="ml-1 text-xs font-normal text-gray-400">
                    ({data.pipeline.summary.readiness_percent}%)
                  </span>
                </span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    data.pipeline.summary.readiness_percent >= 100
                      ? 'bg-emerald-500'
                      : 'bg-blue-500'
                  }`}
                  style={{ width: `${Math.min(100, data.pipeline.summary.readiness_percent)}%` }}
                />
              </div>
              <div className="mt-2 flex items-center justify-between text-xs text-gray-400">
                <span>활성 모델: {data.pipeline.summary.active_model}</span>
                {data.predictions && data.predictions.est_days_to_ready != null && data.predictions.est_days_to_ready > 0 ? (
                  <span>
                    예상 소요: ~{data.predictions.est_days_to_ready}일
                    {data.predictions.est_ready_date_kst && ` (${data.predictions.est_ready_date_kst})`}
                  </span>
                ) : data.pipeline.summary.readiness_percent >= 100 ? (
                  <span className="text-emerald-500">Fine-tuning 준비 완료</span>
                ) : null}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Training Data Stats */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {trainingStats.map((stat) => (
          <Card key={stat.label}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {stat.label}
                  </p>
                  <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-gray-100">
                    {stat.value}
                    {stat.suffix && (
                      <span className="ml-1 text-base font-normal text-gray-400">
                        {stat.suffix}
                      </span>
                    )}
                  </p>
                </div>
                <div
                  className={`flex h-11 w-11 items-center justify-center rounded-xl ${stat.iconBg}`}
                >
                  <stat.icon className={`h-5 w-5 ${stat.iconColor}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Inline Evaluation Activity (Recent 24h) */}
      {data.recent_evaluations && data.recent_evaluations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-orange-500" />
              인라인 평가 활동
              <span className="ml-auto text-xs font-normal text-gray-400">
                최근 24시간 | {data.predictions?.daily_collection_rate ?? data.recent_evaluations.length}건 수집
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="pb-3 pr-4 text-left font-medium text-gray-500 dark:text-gray-400">
                      기사 제목
                    </th>
                    <th className="pb-3 pr-4 text-right font-medium text-gray-500 dark:text-gray-400">
                      품질 점수
                    </th>
                    <th className="pb-3 pr-4 text-left font-medium text-gray-500 dark:text-gray-400">
                      추출 방식
                    </th>
                    <th className="pb-3 text-right font-medium text-gray-500 dark:text-gray-400">
                      수집 시각
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {data.recent_evaluations.map((ev, idx) => (
                    <tr key={idx}>
                      <td className="max-w-xs truncate py-2.5 pr-4 text-gray-900 dark:text-gray-100">
                        {ev.title}
                      </td>
                      <td className="py-2.5 pr-4 text-right">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          ev.quality_score >= 0.8
                            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                            : ev.quality_score >= 0.5
                              ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                              : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                        }`}>
                          {ev.quality_score.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-2.5 pr-4">
                        <span className="inline-flex rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                          {ev.method}
                        </span>
                      </td>
                      <td className="whitespace-nowrap py-2.5 text-right text-xs text-gray-400">
                        {ev.created_at ? formatTimeAgo(ev.created_at) : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Model Versions Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5 text-blue-500" />
            모델 버전 이력
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.model_versions.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="pb-3 pr-4 text-left font-medium text-gray-500 dark:text-gray-400">
                      버전
                    </th>
                    <th className="pb-3 pr-4 text-left font-medium text-gray-500 dark:text-gray-400">
                      기반 모델
                    </th>
                    <th className="pb-3 pr-4 text-right font-medium text-gray-500 dark:text-gray-400">
                      F1
                    </th>
                    <th className="pb-3 pr-4 text-right font-medium text-gray-500 dark:text-gray-400">
                      Precision
                    </th>
                    <th className="pb-3 pr-4 text-right font-medium text-gray-500 dark:text-gray-400">
                      Recall
                    </th>
                    <th className="pb-3 pr-4 text-left font-medium text-gray-500 dark:text-gray-400">
                      상태
                    </th>
                    <th className="pb-3 pr-4 text-right font-medium text-gray-500 dark:text-gray-400">
                      학습 데이터
                    </th>
                    <th className="pb-3 text-left font-medium text-gray-500 dark:text-gray-400">
                      생성일
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {data.model_versions.map((mv) => {
                    const badge = getStatusBadge(mv.status)
                    return (
                      <tr key={mv.version}>
                        <td className="py-2.5 pr-4 font-medium text-gray-900 dark:text-gray-100">
                          {mv.version}
                        </td>
                        <td className="py-2.5 pr-4 text-gray-500 dark:text-gray-400">
                          {mv.base_model}
                        </td>
                        <td className="py-2.5 pr-4 text-right font-mono font-medium text-gray-900 dark:text-gray-100">
                          {formatF1(mv.f1)}
                        </td>
                        <td className="py-2.5 pr-4 text-right font-mono text-gray-500 dark:text-gray-400">
                          {formatF1(mv.precision)}
                        </td>
                        <td className="py-2.5 pr-4 text-right font-mono text-gray-500 dark:text-gray-400">
                          {formatF1(mv.recall)}
                        </td>
                        <td className="py-2.5 pr-4">
                          <span
                            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${badge.bg} ${badge.text}`}
                          >
                            <badge.Icon className="h-3 w-3" />
                            {badge.label}
                          </span>
                        </td>
                        <td className="py-2.5 pr-4 text-right text-gray-500 dark:text-gray-400">
                          {mv.samples.toLocaleString('ko-KR')}건
                        </td>
                        <td className="whitespace-nowrap py-2.5 text-xs text-gray-400">
                          {new Date(mv.created_at).toLocaleString('ko-KR')}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-gray-400">
              모델 버전 이력이 없습니다
            </p>
          )}
        </CardContent>
      </Card>

      {/* Schedule Card (with KST next-run) */}
      {data.schedule && data.schedule.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5 text-indigo-500" />
              MLOps 스케줄
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="pb-3 pr-4 text-left font-medium text-gray-500 dark:text-gray-400">
                      작업
                    </th>
                    <th className="pb-3 pr-4 text-left font-medium text-gray-500 dark:text-gray-400">
                      주기
                    </th>
                    <th className="pb-3 pr-4 text-left font-medium text-gray-500 dark:text-gray-400">
                      다음 실행 (KST)
                    </th>
                    <th className="pb-3 text-left font-medium text-gray-500 dark:text-gray-400">
                      상세
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {data.schedule.map((s) => (
                    <tr key={s.task}>
                      <td className="py-2.5 pr-4 font-medium text-gray-900 dark:text-gray-100">
                        <div className="flex items-center gap-1.5">
                          <Zap className="h-3.5 w-3.5 text-amber-400" />
                          {s.task}
                        </div>
                      </td>
                      <td className="whitespace-nowrap py-2.5 pr-4 text-gray-500 dark:text-gray-400">
                        {s.interval}
                      </td>
                      <td className="whitespace-nowrap py-2.5 pr-4">
                        {s.next_run_kst ? (
                          <span className="inline-flex items-center gap-1 rounded bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">
                            <Clock className="h-3 w-3" />
                            {s.next_run_kst}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400">-</span>
                        )}
                      </td>
                      <td className="py-2.5 text-gray-500 dark:text-gray-400">
                        {s.detail}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Config Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings2 className="h-5 w-5 text-gray-500" />
            MLOps 설정
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-lg border border-gray-100 p-3 dark:border-gray-800">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                최소 품질 기준
              </p>
              <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">
                {data.config.min_quality}
              </p>
            </div>
            <div className="rounded-lg border border-gray-100 p-3 dark:border-gray-800">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                최소 학습 샘플 수
              </p>
              <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">
                {data.config.min_samples.toLocaleString('ko-KR')}
              </p>
            </div>
            <div className="rounded-lg border border-gray-100 p-3 dark:border-gray-800">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                평가 샘플 크기
              </p>
              <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">
                {data.config.eval_sample_size.toLocaleString('ko-KR')}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
