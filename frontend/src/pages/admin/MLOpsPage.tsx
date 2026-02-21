import { useState, useEffect, Fragment } from 'react'
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
  Sparkles,
  ChevronDown,
} from 'lucide-react'
import ReactECharts from 'echarts-for-react'
import echarts from '@/lib/echarts'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import InfoBadge from '@/components/ui/InfoBadge'
import { fetchMLOps } from '@/services/adminApi'

interface ModelVersion {
  version: string
  base_model: string
  f1: number | null
  precision: number | null
  recall: number | null
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

interface NerEntity {
  text: string
  type: string
}

interface RecentEvaluation {
  title: string
  quality_score: number
  method: string
  created_at: string
  original_entities: NerEntity[]
  corrected_entities: NerEntity[]
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

interface QualityAnalytics {
  daily_scores: Array<{
    date: string
    avg_score: number
    count: number
    method_bert: number
    method_kiwi: number
  }>
  entity_error_types: Array<{
    type: string
    label: string
    count: number
    pct: number
  }>
  method_ratio: { bert_ner: number; kiwipiepy: number }
  latest_insight: {
    version: string
    insight: string
    created_at: string
  } | null
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
  quality_analytics?: QualityAnalytics
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

const ENTITY_COLORS: Record<string, string> = {
  PS: '#6366f1',
  OG: '#f59e0b',
  LC: '#10b981',
  DT: '#3b82f6',
  TI: '#8b5cf6',
  QT: '#ef4444',
}

export default function MLOpsPage() {
  const [data, setData] = useState<MLOpsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedEvals, setExpandedEvals] = useState<Set<number>>(new Set())

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

  const qa = data.quality_analytics

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
              <InfoBadge content={"수집 → 평가 → 준비 확인 → Fine-tuning → 배포 → 재추출의 6단계 자동화 루프.\n크롤링 배치마다 GPT-5가 NER 추출 품질을 평가하고, 학습 데이터가 임계치에 도달하면 BERT 모델을 자동으로 재학습합니다."} />
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
                <span className="flex items-center gap-1 text-gray-500 dark:text-gray-400">
                  학습 데이터 진행률
                  <InfoBadge content={"현재까지 축적된 미사용 학습 데이터와 Fine-tuning 트리거 임계치의 비율.\n100%에 도달하면 다음 스케줄(매일 11:00 KST)에 자동으로 Fine-tuning이 시작됩니다."} />
                </span>
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

      {/* ====== Quality Analytics Section ====== */}
      {qa && (
        <>
          {/* Quality Trend Chart — full width */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-cyan-500" />
                NER 품질 추이
                <InfoBadge content={"GPT-5가 매 크롤링 배치에서 5건의 기사를 샘플링하여 NER 추출 품질을 0.0~1.0으로 평가한 일별 평균.\n높을수록 현재 모델의 키워드 추출이 정확함을 의미합니다.\n막대는 해당일 평가된 기사 건수입니다."} />
                <span className="ml-auto text-xs font-normal text-gray-400">최근 30일</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {qa.daily_scores.length > 0 ? (
                <ReactECharts
                  echarts={echarts}
                  notMerge
                  option={{
                    backgroundColor: 'transparent',
                    tooltip: {
                      trigger: 'axis',
                      backgroundColor: '#1f2937',
                      borderColor: '#374151',
                      textStyle: { color: '#e5e7eb', fontSize: 12 },
                    },
                    legend: {
                      data: ['평균 품질', '평가 건수'],
                      textStyle: { color: '#9ca3af', fontSize: 11 },
                      bottom: 0,
                    },
                    grid: { top: 16, right: 48, bottom: 36, left: 48, containLabel: true },
                    xAxis: {
                      type: 'category',
                      data: qa.daily_scores.map((d) => d.date.slice(5)),
                      axisLabel: { color: '#6b7280', fontSize: 10 },
                      axisLine: { lineStyle: { color: '#374151' } },
                    },
                    yAxis: [
                      {
                        type: 'value',
                        name: '품질',
                        min: 0,
                        max: 1,
                        axisLabel: { color: '#6b7280', fontSize: 10, formatter: '{value}' },
                        splitLine: { lineStyle: { color: '#1f2937' } },
                      },
                      {
                        type: 'value',
                        name: '건수',
                        axisLabel: { color: '#6b7280', fontSize: 10 },
                        splitLine: { show: false },
                      },
                    ],
                    series: [
                      {
                        name: '평균 품질',
                        type: 'line',
                        data: qa.daily_scores.map((d) => d.avg_score),
                        smooth: true,
                        symbol: 'circle',
                        symbolSize: 6,
                        lineStyle: { color: '#06b6d4', width: 2 },
                        itemStyle: { color: '#06b6d4' },
                        areaStyle: {
                          color: {
                            type: 'linear',
                            x: 0, y: 0, x2: 0, y2: 1,
                            colorStops: [
                              { offset: 0, color: 'rgba(6,182,212,0.25)' },
                              { offset: 1, color: 'rgba(6,182,212,0.02)' },
                            ],
                          },
                        },
                      },
                      {
                        name: '평가 건수',
                        type: 'bar',
                        yAxisIndex: 1,
                        data: qa.daily_scores.map((d) => d.count),
                        barMaxWidth: 16,
                        itemStyle: { color: 'rgba(99,102,241,0.4)', borderRadius: [2, 2, 0, 0] },
                      },
                    ],
                  }}
                  style={{ height: 260 }}
                  theme="dark"
                />
              ) : (
                <p className="py-12 text-center text-sm text-gray-400">
                  GPT-5 NER 평가 데이터가 축적되면 품질 추이가 표시됩니다
                </p>
              )}
            </CardContent>
          </Card>

          {/* Entity Error + Model F1 — 2 column grid */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {/* Entity Error Pie */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Target className="h-5 w-5 text-amber-500" />
                  엔터티 유형별 오류
                  <InfoBadge content={"GPT-5가 교정한 엔터티의 유형별 분포.\nPS=인물, OG=기관, LC=장소, DT=날짜, TI=시간, QT=수량.\n비율이 높은 유형은 현재 모델이 가장 자주 놓치거나 잘못 추출하는 엔터티입니다."} />
                </CardTitle>
              </CardHeader>
              <CardContent>
                {qa.entity_error_types.length > 0 ? (
                  <ReactECharts
                    echarts={echarts}
                    notMerge
                    option={{
                      backgroundColor: 'transparent',
                      tooltip: {
                        backgroundColor: '#1f2937',
                        borderColor: '#374151',
                        textStyle: { color: '#e5e7eb', fontSize: 12 },
                        formatter: (params: { name: string; value: number; percent: number }) =>
                          `${params.name}: ${params.value}건 (${params.percent}%)`,
                      },
                      series: [
                        {
                          type: 'pie',
                          radius: ['40%', '70%'],
                          avoidLabelOverlap: true,
                          itemStyle: { borderRadius: 4, borderColor: '#0a0a0a', borderWidth: 2 },
                          label: {
                            color: '#9ca3af',
                            fontSize: 11,
                            formatter: '{b}\n{d}%',
                          },
                          emphasis: {
                            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' },
                            label: { fontWeight: 'bold' },
                          },
                          data: qa.entity_error_types.map((e) => ({
                            name: e.label,
                            value: e.count,
                            itemStyle: { color: ENTITY_COLORS[e.type] || '#6b7280' },
                          })),
                        },
                      ],
                    }}
                    style={{ height: 240 }}
                    theme="dark"
                  />
                ) : (
                  <p className="py-12 text-center text-sm text-gray-400">
                    평가 데이터 수집 후 표시됩니다
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Model Version F1 Bar */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Brain className="h-5 w-5 text-blue-500" />
                  모델 성능 비교
                  <InfoBadge content={"Fine-tuning된 각 모델 버전의 F1 점수 비교.\nF1은 정밀도(Precision)와 재현율(Recall)의 조화 평균으로, 1.0에 가까울수록 엔터티 인식이 정확합니다.\n초록색은 현재 활성 모델입니다."} />
                </CardTitle>
              </CardHeader>
              <CardContent>
                {data.model_versions.length > 0 ? (
                  <ReactECharts
                    echarts={echarts}
                    notMerge
                    option={{
                      backgroundColor: 'transparent',
                      tooltip: {
                        backgroundColor: '#1f2937',
                        borderColor: '#374151',
                        textStyle: { color: '#e5e7eb', fontSize: 12 },
                        formatter: (params: { name: string; value: number | null }) =>
                          params.value != null ? `${params.name}: F1 ${(params.value * 100).toFixed(1)}%` : `${params.name}: -`,
                      },
                      grid: { top: 16, right: 16, bottom: 24, left: 48, containLabel: true },
                      xAxis: {
                        type: 'category',
                        data: [...data.model_versions].reverse().map((m) => m.version),
                        axisLabel: { color: '#6b7280', fontSize: 10 },
                        axisLine: { lineStyle: { color: '#374151' } },
                      },
                      yAxis: {
                        type: 'value',
                        min: 0,
                        max: 1,
                        axisLabel: {
                          color: '#6b7280',
                          fontSize: 10,
                          formatter: (v: number) => `${(v * 100).toFixed(0)}%`,
                        },
                        splitLine: { lineStyle: { color: '#1f2937' } },
                      },
                      series: [
                        {
                          type: 'bar',
                          data: [...data.model_versions].reverse().map((m) => ({
                            value: m.f1 ?? 0,
                            itemStyle: {
                              color: m.status === 'active' ? '#10b981' : '#6366f1',
                              borderRadius: [4, 4, 0, 0],
                            },
                          })),
                          barMaxWidth: 36,
                          label: {
                            show: true,
                            position: 'top',
                            formatter: (params: { value: number | null }) =>
                              params.value != null && params.value > 0 ? `${(params.value * 100).toFixed(1)}%` : '-',
                            color: '#9ca3af',
                            fontSize: 10,
                          },
                        },
                      ],
                    }}
                    style={{ height: 240 }}
                    theme="dark"
                  />
                ) : (
                  <p className="py-12 text-center text-sm text-gray-400">
                    Fine-tuning 완료 후 표시됩니다
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Extraction Method Ratio — compact full width */}
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <FlaskConical className="h-5 w-5 text-violet-500" />
                <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                  추출 방식
                </span>
                <InfoBadge content={"BERT NER: klue/bert-base 기반 딥러닝 모델. Fine-tuning 후 NER 전용 모델로 전환됩니다.\nkiwipiepy: 한국어 형태소 분석기 기반 규칙형 추출. Fine-tuning 전이거나 BERT 모델 로딩 실패 시 사용됩니다.\nkiwipiepy 100%는 아직 Fine-tuning된 모델이 없는 초기 상태(정상)이거나, 모델 로딩 문제일 수 있습니다."} />
                <div className="flex flex-1 items-center gap-4">
                  {(() => {
                    const bert = qa.method_ratio.bert_ner
                    const kiwi = qa.method_ratio.kiwipiepy
                    const total = bert + kiwi
                    const bertPct = total > 0 ? Math.round((bert / total) * 100) : 0
                    const kiwiPct = total > 0 ? 100 - bertPct : 0
                    return (
                      <>
                        <div className="flex flex-1 flex-col gap-1">
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-gray-500 dark:text-gray-400">
                              BERT NER <span className="font-medium text-gray-700 dark:text-gray-300">{bert}건</span>
                            </span>
                            <span className="font-medium text-indigo-500">{bertPct}%</span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                            <div
                              className="h-full rounded-full bg-indigo-500 transition-all duration-500"
                              style={{ width: `${bertPct}%` }}
                            />
                          </div>
                        </div>
                        <div className="h-6 w-px bg-gray-200 dark:bg-gray-700" />
                        <div className="flex flex-1 flex-col gap-1">
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-gray-500 dark:text-gray-400">
                              kiwipiepy <span className="font-medium text-gray-700 dark:text-gray-300">{kiwi}건</span>
                            </span>
                            <span className="font-medium text-amber-500">{kiwiPct}%</span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                            <div
                              className="h-full rounded-full bg-amber-500 transition-all duration-500"
                              style={{ width: `${kiwiPct}%` }}
                            />
                          </div>
                        </div>
                      </>
                    )
                  })()}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Deployment Insight — conditional */}
          {qa.latest_insight && (
            <Card className="border-indigo-200 dark:border-indigo-800/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-indigo-500" />
                  배포 인사이트
                  <InfoBadge content="모델이 새 버전으로 교체(promote)될 때 GPT-5가 축적된 품질 데이터, 엔터티 오류 패턴, 모델 히스토리를 종합 분석하여 자동 생성한 인사이트입니다." />
                  <span className="ml-2 inline-flex rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">
                    {qa.latest_insight.version}
                  </span>
                  {qa.latest_insight.created_at && (
                    <span className="ml-auto text-xs font-normal text-gray-400">
                      {formatTimeAgo(qa.latest_insight.created_at)}
                    </span>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="whitespace-pre-line text-sm leading-relaxed text-gray-700 dark:text-gray-300">
                  {qa.latest_insight.insight}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Inline Evaluation Activity (Recent 24h) */}
      {data.recent_evaluations && data.recent_evaluations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-orange-500" />
              인라인 평가 활동
              <InfoBadge content={"크롤링 배치(30분 간격)마다 5건을 샘플링하여 GPT-5 function calling으로 NER 품질을 평가한 결과.\n품질 점수는 현재 모델의 추출 정확도(0.0~1.0)이며, 교정된 엔터티는 학습 데이터로 축적됩니다.\n행을 클릭하면 현재 모델이 추출한 키워드와 GPT-5가 교정한 키워드를 비교할 수 있습니다.\nFine-tuning이 반복될수록 모델 추출 결과가 GPT-5 교정 결과에 가까워집니다."} />
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
                  {data.recent_evaluations.map((ev, idx) => {
                    const isExpanded = expandedEvals.has(idx)
                    const hasEntities = (ev.original_entities?.length > 0 || ev.corrected_entities?.length > 0)
                    return (
                      <Fragment key={idx}>
                        <tr
                          className={hasEntities ? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50' : ''}
                          onClick={() => {
                            if (!hasEntities) return
                            setExpandedEvals((prev) => {
                              if (prev.has(idx)) return new Set()
                              return new Set([idx])
                            })
                          }}
                        >
                          <td className="max-w-xs py-2.5 pr-4">
                            <div className="flex items-center gap-1.5 overflow-hidden">
                              {hasEntities && (
                                <ChevronDown className={`h-3.5 w-3.5 shrink-0 text-gray-400 transition-transform ${isExpanded ? 'rotate-0' : '-rotate-90'}`} />
                              )}
                              <span className="truncate text-gray-900 dark:text-gray-100">{ev.title}</span>
                            </div>
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
                        {isExpanded && hasEntities && (
                          <tr>
                            <td colSpan={4} className="pb-3 pt-0">
                              <div className="grid grid-cols-2 gap-3 rounded-lg border border-gray-100 bg-gray-50/50 p-3 dark:border-gray-700 dark:bg-gray-800/30">
                                <div>
                                  <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
                                    현재 모델 추출
                                  </p>
                                  <div className="flex flex-wrap gap-1">
                                    {ev.original_entities?.length > 0 ? ev.original_entities.map((e, i) => (
                                      <span
                                        key={i}
                                        className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-xs"
                                        style={{
                                          backgroundColor: `${ENTITY_COLORS[e.type] || '#6b7280'}18`,
                                          color: ENTITY_COLORS[e.type] || '#6b7280',
                                        }}
                                      >
                                        {e.text}
                                        <span className="text-[9px] opacity-60">{e.type}</span>
                                      </span>
                                    )) : (
                                      <span className="text-xs italic text-gray-400">데이터 수집 전</span>
                                    )}
                                  </div>
                                </div>
                                <div>
                                  <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-500">
                                    GPT-5 교정
                                  </p>
                                  <div className="flex flex-wrap gap-1">
                                    {ev.corrected_entities?.length > 0 ? ev.corrected_entities.map((e, i) => (
                                      <span
                                        key={i}
                                        className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-xs"
                                        style={{
                                          backgroundColor: `${ENTITY_COLORS[e.type] || '#6b7280'}18`,
                                          color: ENTITY_COLORS[e.type] || '#6b7280',
                                        }}
                                      >
                                        {e.text}
                                        <span className="text-[9px] opacity-60">{e.type}</span>
                                      </span>
                                    )) : (
                                      <span className="text-xs text-gray-400">없음</span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
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
              <p className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400">
                최소 품질 기준
                <InfoBadge content="GPT-5 평가에서 이 점수 이상인 샘플만 학습 데이터로 사용됩니다. 낮은 품질의 교정 데이터가 모델을 오염시키는 것을 방지합니다." side="right" />
              </p>
              <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">
                {data.config.min_quality}
              </p>
            </div>
            <div className="rounded-lg border border-gray-100 p-3 dark:border-gray-800">
              <p className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400">
                최소 학습 샘플 수
                <InfoBadge content="이 수치만큼 학습 데이터가 축적되어야 자동 Fine-tuning이 트리거됩니다. 너무 적은 데이터로 학습하면 과적합(overfitting) 위험이 있습니다." side="right" />
              </p>
              <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">
                {data.config.min_samples.toLocaleString('ko-KR')}
              </p>
            </div>
            <div className="rounded-lg border border-gray-100 p-3 dark:border-gray-800">
              <p className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400">
                평가 샘플 크기
                <InfoBadge content="크롤링 배치당 GPT-5로 평가하는 기사 수. 높을수록 학습 데이터가 빠르게 쌓이지만 API 비용이 증가합니다." side="right" />
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
