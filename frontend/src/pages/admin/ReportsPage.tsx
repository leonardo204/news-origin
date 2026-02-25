import { useState, useEffect, useCallback } from 'react'
import { fetchReports, fetchReportDetail } from '@/services/adminApi'
import {
  Mail,
  Calendar,
  AlertTriangle,
  AlertCircle,
  Info,
  ChevronLeft,
  ChevronRight,
  Filter,
  RefreshCw,
  Clock,
  CheckCircle2,
  XCircle,
  TrendingUp,
  TrendingDown,
  Minus,
  Newspaper,
  Globe,
  Cpu,
  Activity,
  ShieldAlert,
  Sparkles,
  FileText,
  ArrowLeft,
} from 'lucide-react'

/* ─── Types ─── */
interface ReportSummary {
  id: string
  report_type: string
  title: string
  summary: string
  category: string
  severity: string
  email_sent: boolean
  created_at: string | null
}

interface ReportDetail extends ReportSummary {
  content_json: Record<string, unknown>
  email_sent_at: string | null
  email_error: string | null
}

/* ─── Constants ─── */
const TYPE_LABELS: Record<string, string> = { weekly: '주간', monthly: '월간', alert: '알림', mlops: 'MLOps' }
const SEVERITY_CONFIG: Record<string, { color: string; darkColor: string; icon: typeof Info }> = {
  info: { color: 'bg-blue-100 text-blue-700', darkColor: 'dark:bg-blue-500/10 dark:text-blue-400', icon: Info },
  warning: { color: 'bg-amber-100 text-amber-700', darkColor: 'dark:bg-amber-500/10 dark:text-amber-400', icon: AlertTriangle },
  critical: { color: 'bg-red-100 text-red-700', darkColor: 'dark:bg-red-500/10 dark:text-red-400', icon: AlertCircle },
}
const PAGE_SIZE = 20

/* ─── Helpers ─── */
function formatDate(iso: string | null): string {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function formatRelative(iso: string | null): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return '방금 전'
  if (min < 60) return `${min}분 전`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}시간 전`
  const day = Math.floor(hr / 24)
  return `${day}일 전`
}

function fmtNum(n: number | null | undefined): string {
  if (n == null) return '-'
  return n.toLocaleString('ko-KR')
}

function ChangeIndicator({ rate }: { rate: number | null | undefined }) {
  if (rate == null) return <span className="text-xs text-gray-400">-</span>
  const isUp = rate > 0
  const isDown = rate < 0
  const Icon = isUp ? TrendingUp : isDown ? TrendingDown : Minus
  const color = isUp ? 'text-green-600 dark:text-green-400' : isDown ? 'text-red-600 dark:text-red-400' : 'text-gray-400'
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${color}`}>
      <Icon className="h-3 w-3" />
      {isUp ? '+' : ''}{rate}%
    </span>
  )
}

function ProgressBar({ percent, label, sub }: { percent: number; label: string; sub: string }) {
  const color = percent >= 90 ? 'bg-red-500' : percent >= 70 ? 'bg-amber-500' : 'bg-green-500'
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-600 dark:text-gray-300">{label}</span>
        <span className="font-medium text-gray-900 dark:text-gray-100">{percent}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(percent, 100)}%` }} />
      </div>
      <span className="text-[10px] text-gray-400">{sub}</span>
    </div>
  )
}

function SectionCard({ title, icon: Icon, children, error }: { title: string; icon: typeof Info; children: React.ReactNode; error?: string }) {
  if (error) {
    return (
      <div className="rounded-lg border border-gray-100 dark:border-gray-800">
        <div className="flex items-center gap-2 border-b border-gray-100 bg-gray-50 px-4 py-2.5 dark:border-gray-800 dark:bg-gray-800/50">
          <Icon className="h-4 w-4 text-gray-400" />
          <span className="text-xs font-semibold text-gray-600 dark:text-gray-300">{title}</span>
        </div>
        <div className="px-4 py-3 text-xs text-gray-400">데이터 수집 실패: {error}</div>
      </div>
    )
  }
  return (
    <div className="rounded-lg border border-gray-100 dark:border-gray-800">
      <div className="flex items-center gap-2 border-b border-gray-100 bg-gray-50 px-4 py-2.5 dark:border-gray-800 dark:bg-gray-800/50">
        <Icon className="h-4 w-4 text-gray-400" />
        <span className="text-xs font-semibold text-gray-600 dark:text-gray-300">{title}</span>
      </div>
      <div className="px-4 py-3">{children}</div>
    </div>
  )
}

function StatBox({ label, value, sub }: { label: string; value: string; sub?: React.ReactNode }) {
  return (
    <div className="rounded-md bg-gray-50 px-3 py-2 dark:bg-gray-800/50">
      <div className="text-[10px] uppercase tracking-wider text-gray-400">{label}</div>
      <div className="mt-0.5 text-sm font-semibold text-gray-900 dark:text-gray-100">{value}</div>
      {sub && <div className="mt-0.5">{sub}</div>}
    </div>
  )
}

/* ─── Section Renderers ─── */
function CrawlingSection({ data }: { data: Record<string, unknown> }) {
  if (!data || data.error) return <SectionCard title="크롤링" icon={Newspaper} error={data?.error as string} children={null} />
  const d = data as {
    total_articles: number; prev_total_articles: number; change_rate: number | null
    category_distribution: { category: string; count: number }[]
    top_publishers: { name: string; count: number }[]
  }
  return (
    <SectionCard title="뉴스 수집 현황" icon={Newspaper}>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <StatBox label="수집 기사" value={`${fmtNum(d.total_articles)}건`} sub={<ChangeIndicator rate={d.change_rate} />} />
        <StatBox label="이전 기간" value={`${fmtNum(d.prev_total_articles)}건`} />
        <StatBox label="카테고리" value={`${d.category_distribution?.length || 0}개`} />
      </div>
      {d.category_distribution?.length > 0 && (
        <div className="mt-3">
          <div className="mb-1.5 text-[10px] uppercase tracking-wider text-gray-400">카테고리별 수집</div>
          <div className="space-y-1">
            {d.category_distribution.map((c) => {
              const pct = d.total_articles > 0 ? Math.round(c.count / d.total_articles * 100) : 0
              return (
                <div key={c.category} className="flex items-center gap-2 text-xs">
                  <span className="w-16 shrink-0 text-gray-600 dark:text-gray-300">{c.category}</span>
                  <div className="flex-1">
                    <div className="h-1.5 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
                      <div className="h-full rounded-full bg-blue-400" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                  <span className="w-16 text-right font-medium text-gray-700 dark:text-gray-300">{fmtNum(c.count)}건</span>
                  <span className="w-10 text-right text-gray-400">{pct}%</span>
                </div>
              )
            })}
          </div>
        </div>
      )}
      {d.top_publishers?.length > 0 && (
        <div className="mt-3">
          <div className="mb-1.5 text-[10px] uppercase tracking-wider text-gray-400">상위 언론사</div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            {d.top_publishers.map((p, i) => (
              <div key={p.name} className="flex items-center justify-between">
                <span className="text-gray-600 dark:text-gray-300">
                  <span className="mr-1 text-gray-400">{i + 1}.</span>{p.name}
                </span>
                <span className="font-medium text-gray-700 dark:text-gray-300">{fmtNum(p.count)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </SectionCard>
  )
}

function TrafficSection({ data }: { data: Record<string, unknown> }) {
  if (!data || data.error) return <SectionCard title="트래픽" icon={Globe} error={data?.error as string} children={null} />
  const d = data as {
    total_requests: number; prev_total_requests: number; change_rate: number | null
    error_count: number; error_rate: number; avg_duration_ms: number; unique_ips: number
    top_endpoints: { method: string; path: string; count: number; avg_ms: number }[]
    status_distribution: { code: number; count: number }[]
  }
  return (
    <SectionCard title="방문자 트래픽" icon={Globe}>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <StatBox label="총 요청" value={`${fmtNum(d.total_requests)}건`} sub={<ChangeIndicator rate={d.change_rate} />} />
        <StatBox label="에러율" value={`${d.error_rate}%`} sub={<span className="text-[10px] text-gray-400">{fmtNum(d.error_count)}건</span>} />
        <StatBox label="평균 응답" value={`${d.avg_duration_ms}ms`} />
        <StatBox label="고유 방문자" value={`${fmtNum(d.unique_ips)}명`} />
      </div>
      {d.status_distribution?.length > 0 && (
        <div className="mt-3">
          <div className="mb-1.5 text-[10px] uppercase tracking-wider text-gray-400">응답 코드 분포</div>
          <div className="flex flex-wrap gap-2">
            {d.status_distribution.map((s) => {
              const color = s.code < 300 ? 'bg-green-100 text-green-700 dark:bg-green-500/10 dark:text-green-400'
                : s.code < 400 ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400'
                : s.code < 500 ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400'
                : 'bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400'
              return (
                <span key={s.code} className={`rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
                  {s.code}: {fmtNum(s.count)}건
                </span>
              )
            })}
          </div>
        </div>
      )}
      {d.top_endpoints?.length > 0 && (
        <div className="mt-3">
          <div className="mb-1.5 text-[10px] uppercase tracking-wider text-gray-400">주요 엔드포인트</div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100 text-left text-gray-400 dark:border-gray-800">
                  <th className="pb-1 font-medium">경로</th>
                  <th className="pb-1 text-right font-medium">요청수</th>
                  <th className="pb-1 text-right font-medium">응답시간</th>
                </tr>
              </thead>
              <tbody className="text-gray-600 dark:text-gray-300">
                {d.top_endpoints.map((ep) => (
                  <tr key={`${ep.method}-${ep.path}`} className="border-b border-gray-50 dark:border-gray-800/50">
                    <td className="py-1"><span className="mr-1 text-gray-400">{ep.method}</span>{ep.path}</td>
                    <td className="py-1 text-right font-medium">{fmtNum(ep.count)}</td>
                    <td className="py-1 text-right">{ep.avg_ms}ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </SectionCard>
  )
}

function MLOpsSection({ data }: { data: Record<string, unknown> }) {
  if (!data || data.error) return <SectionCard title="MLOps" icon={Activity} error={data?.error as string} children={null} />
  const d = data as {
    new_training_samples: number; total_training_samples: number
    avg_quality_score: number | null; prev_avg_quality_score: number | null
    active_model: string; active_model_f1: number | null
    model_history: { version: string; f1: number | null; status: string; is_active: boolean; created_at: string | null }[]
    quality_trend: { date: string; avg_score: number; count: number }[]
  }
  const qualityChange = d.avg_quality_score != null && d.prev_avg_quality_score != null && d.prev_avg_quality_score > 0
    ? mathRound((d.avg_quality_score - d.prev_avg_quality_score) / d.prev_avg_quality_score * 100, 1)
    : null
  return (
    <SectionCard title="AI 키워드 추출 (MLOps)" icon={Activity}>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <StatBox label="신규 학습 데이터" value={`+${fmtNum(d.new_training_samples)}건`} sub={<span className="text-[10px] text-gray-400">총 {fmtNum(d.total_training_samples)}건</span>} />
        <StatBox label="평균 품질 점수" value={d.avg_quality_score != null ? d.avg_quality_score.toFixed(3) : '-'} sub={qualityChange != null ? <ChangeIndicator rate={qualityChange} /> : undefined} />
        <StatBox label="활성 모델" value={d.active_model} sub={d.active_model_f1 != null ? <span className="text-[10px] text-gray-400">F1: {d.active_model_f1}</span> : undefined} />
      </div>
      {d.quality_trend?.length > 0 && (
        <div className="mt-3">
          <div className="mb-1.5 text-[10px] uppercase tracking-wider text-gray-400">일별 품질 추이</div>
          <div className="flex items-end gap-px" style={{ height: 40 }}>
            {d.quality_trend.map((q) => {
              const h = Math.max(4, Math.round(q.avg_score * 40))
              return (
                <div key={q.date} className="group relative flex-1" title={`${q.date}: ${q.avg_score.toFixed(3)} (${q.count}건)`}>
                  <div className="mx-auto w-full max-w-[8px] rounded-t bg-blue-400 transition-colors group-hover:bg-blue-600" style={{ height: h }} />
                </div>
              )
            })}
          </div>
          <div className="mt-0.5 flex justify-between text-[9px] text-gray-400">
            <span>{d.quality_trend[0]?.date?.slice(5)}</span>
            <span>{d.quality_trend[d.quality_trend.length - 1]?.date?.slice(5)}</span>
          </div>
        </div>
      )}
      {d.model_history?.length > 0 && (
        <div className="mt-3">
          <div className="mb-1.5 text-[10px] uppercase tracking-wider text-gray-400">모델 이력</div>
          <div className="space-y-1">
            {d.model_history.map((m) => (
              <div key={m.version} className={`flex items-center justify-between rounded px-2 py-1 text-xs ${m.is_active ? 'bg-green-50 dark:bg-green-500/5' : ''}`}>
                <div className="flex items-center gap-2">
                  <span className={`font-medium ${m.is_active ? 'text-green-700 dark:text-green-400' : 'text-gray-600 dark:text-gray-300'}`}>{m.version}</span>
                  {m.is_active && <span className="rounded bg-green-100 px-1 py-0.5 text-[10px] text-green-700 dark:bg-green-500/10 dark:text-green-400">활성</span>}
                  <span className="text-gray-400">{m.status}</span>
                </div>
                <span className="text-gray-500">{m.f1 != null ? `F1: ${m.f1}` : '-'}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </SectionCard>
  )
}

function SystemSection({ data }: { data: Record<string, unknown> }) {
  if (!data || data.error) return <SectionCard title="시스템" icon={Cpu} error={data?.error as string} children={null} />
  const d = data as {
    cpu_percent: number; memory_percent: number; memory_total_gb: number; memory_used_gb: number
    disk_percent: number; disk_total_gb: number; disk_used_gb: number; disk_free_gb: number
  }
  return (
    <SectionCard title="서버 리소스" icon={Cpu}>
      <div className="space-y-3">
        <ProgressBar percent={d.cpu_percent} label="CPU 사용률" sub={`${d.cpu_percent}%`} />
        <ProgressBar
          percent={d.memory_percent}
          label="메모리"
          sub={d.memory_total_gb ? `${d.memory_used_gb}GB / ${d.memory_total_gb}GB` : `${d.memory_percent}%`}
        />
        <ProgressBar
          percent={d.disk_percent}
          label="디스크"
          sub={d.disk_total_gb ? `${d.disk_used_gb}GB / ${d.disk_total_gb}GB (여유 ${d.disk_free_gb}GB)` : `${d.disk_percent}%`}
        />
      </div>
    </SectionCard>
  )
}

function ErrorsSection({ data }: { data: Record<string, unknown> }) {
  if (!data || data.error) return null
  const d = data as { total_errors: number; top_errors: { path: string; status_code: number; count: number }[] }
  if (!d.top_errors?.length && !d.total_errors) return null
  return (
    <SectionCard title="에러 현황" icon={ShieldAlert}>
      <div className="mb-2">
        <span className="text-xs text-gray-500 dark:text-gray-400">총 에러: <span className="font-medium text-gray-900 dark:text-gray-100">{fmtNum(d.total_errors)}건</span></span>
      </div>
      {d.top_errors?.length > 0 ? (
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-100 text-left text-gray-400 dark:border-gray-800">
              <th className="pb-1 font-medium">경로</th>
              <th className="pb-1 text-center font-medium">코드</th>
              <th className="pb-1 text-right font-medium">건수</th>
            </tr>
          </thead>
          <tbody className="text-gray-600 dark:text-gray-300">
            {d.top_errors.map((e, i) => (
              <tr key={i} className="border-b border-gray-50 dark:border-gray-800/50">
                <td className="py-1">{e.path}</td>
                <td className="py-1 text-center">
                  <span className={`rounded px-1 py-0.5 text-[10px] font-medium ${
                    e.status_code >= 500 ? 'bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400'
                      : 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400'
                  }`}>{e.status_code}</span>
                </td>
                <td className="py-1 text-right font-medium">{fmtNum(e.count)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-xs text-gray-400">에러 없음</p>
      )}
    </SectionCard>
  )
}

/* ─── Fine-tuning Report Renderer ─── */
function FinetuneReportSection({ content }: { content: Record<string, unknown> }) {
  const training = content.training as { version: string; base_model: string; continual_learning: boolean; train_samples: number; val_samples: number } | undefined
  const evaluation = content.evaluation as { f1: number; precision: number; recall: number; metric_type: string } | undefined
  const qualityGate = content.quality_gate as { promoted: boolean; current_f1: number | null; current_metric_type: string | null; f1_improvement: number | null; decision_reason: string } | undefined
  const deploymentInsight = content.deployment_insight as string | undefined

  return (
    <div className="space-y-3">
      {/* 학습 설정 */}
      {training && (
        <SectionCard title="학습 설정" icon={Activity}>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <StatBox label="모델 버전" value={training.version} />
            <StatBox label="학습 데이터" value={`${fmtNum(training.train_samples)}건`} />
            <StatBox label="검증 데이터" value={`${fmtNum(training.val_samples)}건`} />
            <StatBox label="기반 모델" value={training.base_model.split('/').pop() || training.base_model} sub={
              <span className="text-[10px] text-gray-400">{training.continual_learning ? '이어 학습' : '처음부터 학습'}</span>
            } />
          </div>
        </SectionCard>
      )}

      {/* 평가 결과 */}
      {evaluation && (
        <SectionCard title="평가 결과" icon={Activity}>
          <div className="grid grid-cols-3 gap-2">
            <StatBox label="F1 Score" value={evaluation.f1.toFixed(4)} sub={
              <span className="text-[10px] text-gray-400">{evaluation.metric_type === 'entity' ? 'entity-level' : 'token-level'}</span>
            } />
            <StatBox label="Precision" value={evaluation.precision.toFixed(4)} />
            <StatBox label="Recall" value={evaluation.recall.toFixed(4)} />
          </div>
        </SectionCard>
      )}

      {/* 품질 검증 */}
      {qualityGate && (
        <SectionCard title="품질 검증 (Quality Gate)" icon={qualityGate.promoted ? CheckCircle2 : XCircle}>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <StatBox label="승격 여부" value={qualityGate.promoted ? '승격 완료' : '승격 거부'} sub={
              qualityGate.promoted
                ? <span className="inline-flex items-center gap-0.5 text-[10px] text-green-600 dark:text-green-400"><CheckCircle2 className="h-3 w-3" />품질 기준 충족</span>
                : <span className="inline-flex items-center gap-0.5 text-[10px] text-red-600 dark:text-red-400"><XCircle className="h-3 w-3" />기준 미달</span>
            } />
            <StatBox label="이전 모델 F1" value={qualityGate.current_f1 != null ? qualityGate.current_f1.toFixed(4) : 'N/A (첫 모델)'} sub={
              qualityGate.current_metric_type
                ? <span className="text-[10px] text-gray-400">{qualityGate.current_metric_type}</span>
                : undefined
            } />
            <StatBox label="F1 개선폭" value={qualityGate.f1_improvement != null ? `${qualityGate.f1_improvement >= 0 ? '+' : ''}${qualityGate.f1_improvement.toFixed(4)}` : '-'} sub={
              qualityGate.f1_improvement != null
                ? <ChangeIndicator rate={qualityGate.current_f1 && qualityGate.current_f1 > 0 ? mathRound(qualityGate.f1_improvement / qualityGate.current_f1 * 100, 1) : null} />
                : undefined
            } />
          </div>
          {qualityGate.decision_reason && (
            <div className="mt-2 rounded bg-gray-50 px-3 py-2 text-xs text-gray-600 dark:bg-gray-800/50 dark:text-gray-300">
              {qualityGate.decision_reason}
            </div>
          )}
        </SectionCard>
      )}

      {/* 배포 인사이트 */}
      {deploymentInsight && (
        <div className="rounded-lg border border-purple-100 bg-purple-50/50 px-4 py-3 dark:border-purple-500/20 dark:bg-purple-500/5">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-purple-700 dark:text-purple-400">
            <Sparkles className="h-3.5 w-3.5" />
            배포 인사이트
          </div>
          <div className="whitespace-pre-line text-xs leading-relaxed text-purple-900 dark:text-purple-200">
            {deploymentInsight}
          </div>
        </div>
      )}
    </div>
  )
}

/* ─── Alert Detail Renderer ─── */
function AlertDetailSection({ content, category }: { content: Record<string, unknown>; category: string }) {
  const recommendation = content.recommendation as string | undefined
  const categoryLabels: Record<string, string> = {
    traffic: '서버 에러율 급증',
    traffic_spike: '트래픽 급증',
    system: '디스크 사용률 경고',
    system_memory: '메모리 사용률 경고',
  }
  const metricEntries = Object.entries(content).filter(
    ([k]) => !['recommendation', 'occurred_at'].includes(k)
  )
  return (
    <div className="space-y-3">
      <SectionCard title={categoryLabels[category] || category} icon={AlertTriangle}>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {metricEntries.map(([k, v]) => {
            const label: Record<string, string> = {
              error_rate: '에러율', total_requests: '총 요청', error_count: '에러 건수',
              threshold: '임계치', period: '측정 기간',
              current_hourly: '현재 시간당', avg_hourly: '평균 시간당', multiplier: '급증 배율',
              disk_percent: '디스크 사용률', disk_total_gb: '전체 용량', disk_used_gb: '사용 중', disk_free_gb: '여유 공간',
              memory_percent: '메모리 사용률', memory_total_gb: '전체', memory_used_gb: '사용 중',
            }
            const display = typeof v === 'number'
              ? (k.includes('rate') || k.includes('percent')) ? `${v}%`
                : k.includes('gb') ? `${v}GB`
                : k.includes('multiplier') ? `${v}배`
                : fmtNum(v) + (k.includes('count') || k.includes('requests') || k.includes('hourly') ? '건' : '')
              : String(v ?? '-')
            return <StatBox key={k} label={label[k] || k} value={display} />
          })}
        </div>
      </SectionCard>
      {recommendation && (
        <div className="rounded-lg border border-blue-100 bg-blue-50/50 px-4 py-3 dark:border-blue-500/20 dark:bg-blue-500/5">
          <div className="mb-1 flex items-center gap-1.5 text-xs font-medium text-blue-700 dark:text-blue-400">
            <Info className="h-3.5 w-3.5" />
            대응 가이드
          </div>
          <p className="text-xs leading-relaxed text-blue-600 dark:text-blue-300">{recommendation}</p>
        </div>
      )}
    </div>
  )
}

/* ─── Helper ─── */
function mathRound(n: number, d: number): number {
  const f = Math.pow(10, d)
  return Math.round(n * f) / f
}

/* ─────────────────────────────────────
   Detail View (게시판 상세 — inline)
   ───────────────────────────────────── */
function ReportDetailView({ report, onBack }: { report: ReportDetail; onBack: () => void }) {
  const sev = SEVERITY_CONFIG[report.severity] || SEVERITY_CONFIG.info
  const isTest = report.title.includes('[테스트]')
  const displayTitle = report.title.replace('[테스트] ', '')

  return (
    <div className="space-y-4">
      {/* Back button */}
      <button
        onClick={onBack}
        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-800 dark:hover:text-gray-300"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        목록으로
      </button>

      {/* Header card */}
      <div className="rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
        <div className="border-b border-gray-100 px-5 py-4 dark:border-gray-800">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
              report.report_type === 'alert'
                ? 'bg-orange-100 text-orange-700 dark:bg-orange-500/10 dark:text-orange-400'
                : report.report_type === 'mlops'
                  ? 'bg-purple-100 text-purple-700 dark:bg-purple-500/10 dark:text-purple-400'
                  : 'bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400'
            }`}>
              {TYPE_LABELS[report.report_type] || report.report_type}
            </span>
            <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${sev.color} ${sev.darkColor}`}>
              {report.severity === 'info' ? '정보' : report.severity === 'warning' ? '경고' : '심각'}
            </span>
            {isTest && (
              <span className="rounded bg-gray-200 px-1.5 py-0.5 text-[10px] text-gray-500 dark:bg-gray-700 dark:text-gray-400">테스트</span>
            )}
          </div>
          <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">{displayTitle}</h3>
          <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatDate(report.created_at)}
            </span>
            <span className="flex items-center gap-1">
              <Mail className="h-3 w-3" />
              {report.email_sent
                ? `발송 완료 (${formatDate(report.email_sent_at)})`
                : report.email_error
                  ? `발송 실패: ${report.email_error}`
                  : 'SMTP 미설정 — 미발송'}
            </span>
          </div>
        </div>

        {/* Body */}
        <div className="space-y-4 px-5 py-4">
          {/* GPT-5 Narrative */}
          {typeof report.content_json?.narrative === 'string' && (
            <div className="rounded-lg border border-indigo-100 bg-indigo-50/50 px-4 py-3 dark:border-indigo-500/20 dark:bg-indigo-500/5">
              <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-indigo-700 dark:text-indigo-400">
                <Sparkles className="h-3.5 w-3.5" />
                AI 운영 요약
              </div>
              <div className="whitespace-pre-line text-xs leading-relaxed text-indigo-900 dark:text-indigo-200">
                {report.content_json.narrative}
              </div>
            </div>
          )}

          {/* Summary */}
          <div className="rounded-lg bg-gray-50 p-4 dark:bg-gray-800/50">
            <div className="mb-1.5 flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-gray-400">
              <FileText className="h-3 w-3" />
              요약
            </div>
            <div className="whitespace-pre-line text-xs leading-relaxed text-gray-700 dark:text-gray-300">
              {report.summary}
            </div>
          </div>

          {/* Content sections — branch by report type */}
          {report.report_type === 'alert' ? (
            <AlertDetailSection content={report.content_json} category={report.category} />
          ) : report.report_type === 'mlops' ? (
            <FinetuneReportSection content={report.content_json} />
          ) : (
            <div className="space-y-3">
              {report.content_json?.period != null && typeof report.content_json.period === 'object' && (
                <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                  <Calendar className="h-3.5 w-3.5" />
                  <span>
                    분석 기간: {formatDate((report.content_json.period as { start: string }).start)} ~ {formatDate((report.content_json.period as { end: string }).end)}
                  </span>
                </div>
              )}
              <CrawlingSection data={report.content_json?.crawling as Record<string, unknown>} />
              <TrafficSection data={report.content_json?.traffic as Record<string, unknown>} />
              <MLOpsSection data={report.content_json?.mlops as Record<string, unknown>} />
              <SystemSection data={report.content_json?.system as Record<string, unknown>} />
              <ErrorsSection data={report.content_json?.errors as Record<string, unknown>} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─────────────────────────────────────
   Main Component
   ───────────────────────────────────── */
export default function ReportsPage() {
  const [reports, setReports] = useState<ReportSummary[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filterType, setFilterType] = useState<string>('')
  const [filterSeverity, setFilterSeverity] = useState<string>('')
  const [selectedReport, setSelectedReport] = useState<ReportDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const loadReports = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = { limit: PAGE_SIZE, offset: page * PAGE_SIZE }
      if (filterType) params.report_type = filterType
      if (filterSeverity) params.severity = filterSeverity
      const { data } = await fetchReports(params)
      setReports(data.reports)
      setTotal(data.total)
    } catch (e) {
      console.error('Failed to load reports:', e)
    } finally {
      setLoading(false)
    }
  }, [page, filterType, filterSeverity])

  useEffect(() => { loadReports() }, [loadReports])

  const openDetail = async (id: string) => {
    setDetailLoading(true)
    try {
      const { data } = await fetchReportDetail(id)
      setSelectedReport(data)
    } catch (e) {
      console.error('Failed to load report detail:', e)
    } finally {
      setDetailLoading(false)
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  /* ─── Detail view (게시판 상세) ─── */
  if (detailLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    )
  }

  if (selectedReport) {
    return <ReportDetailView report={selectedReport} onBack={() => setSelectedReport(null)} />
  }

  /* ─── List view (게시판 목록) ─── */
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <Mail className="h-5 w-5 text-blue-600 dark:text-blue-400" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">리포트</h2>
          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-400">
            {total}건
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            <Filter className="h-3.5 w-3.5 text-gray-400" />
            <select
              value={filterType}
              onChange={(e) => { setFilterType(e.target.value); setPage(0) }}
              className="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs text-gray-700 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
            >
              <option value="">전체 유형</option>
              <option value="weekly">주간</option>
              <option value="monthly">월간</option>
              <option value="alert">알림</option>
              <option value="mlops">MLOps</option>
            </select>
          </div>
          <select
            value={filterSeverity}
            onChange={(e) => { setFilterSeverity(e.target.value); setPage(0) }}
            className="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs text-gray-700 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
          >
            <option value="">전체 등급</option>
            <option value="info">정보</option>
            <option value="warning">경고</option>
            <option value="critical">심각</option>
          </select>
          <button
            onClick={loadReports}
            disabled={loading}
            className="rounded-md p-1.5 text-gray-500 transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
            title="새로고침"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Report list */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
        <div className="hidden border-b border-gray-100 bg-gray-50 px-4 py-2.5 text-xs font-medium text-gray-500 dark:border-gray-800 dark:bg-gray-900/50 dark:text-gray-400 sm:grid sm:grid-cols-[1fr_80px_80px_60px_140px]">
          <span>제목</span>
          <span className="text-center">유형</span>
          <span className="text-center">등급</span>
          <span className="text-center">메일</span>
          <span className="text-right">날짜</span>
        </div>
        {loading && reports.length === 0 ? (
          <div className="flex items-center justify-center py-16 text-sm text-gray-400">
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> 불러오는 중...
          </div>
        ) : reports.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-sm text-gray-400">
            <Mail className="mb-2 h-8 w-8" />
            <p>리포트가 없습니다</p>
          </div>
        ) : (
          <ul className="divide-y divide-gray-100 dark:divide-gray-800">
            {reports.map((r) => {
              const sev = SEVERITY_CONFIG[r.severity] || SEVERITY_CONFIG.info
              const SevIcon = sev.icon
              const isTest = r.title.includes('[테스트]')
              return (
                <li
                  key={r.id}
                  onClick={() => openDetail(r.id)}
                  className="cursor-pointer px-4 py-3 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50 sm:grid sm:grid-cols-[1fr_80px_80px_60px_140px] sm:items-center"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
                      {isTest && <span className="mr-1.5 rounded bg-gray-200 px-1 py-0.5 text-[10px] text-gray-500 dark:bg-gray-700 dark:text-gray-400">테스트</span>}
                      {r.title.replace('[테스트] ', '')}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">
                      {r.summary.split('\n')[0]}
                    </p>
                  </div>
                  <div className="mt-1 flex items-center justify-center sm:mt-0">
                    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                      r.report_type === 'alert'
                        ? 'bg-orange-100 text-orange-700 dark:bg-orange-500/10 dark:text-orange-400'
                        : r.report_type === 'mlops'
                          ? 'bg-purple-100 text-purple-700 dark:bg-purple-500/10 dark:text-purple-400'
                          : 'bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400'
                    }`}>
                      {r.report_type === 'alert' ? <AlertTriangle className="h-3 w-3" /> : r.report_type === 'mlops' ? <Activity className="h-3 w-3" /> : <Calendar className="h-3 w-3" />}
                      {TYPE_LABELS[r.report_type] || r.report_type}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center justify-center sm:mt-0">
                    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${sev.color} ${sev.darkColor}`}>
                      <SevIcon className="h-3 w-3" />
                      {r.severity === 'info' ? '정보' : r.severity === 'warning' ? '경고' : '심각'}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center justify-center sm:mt-0" title={r.email_sent ? '발송 완료' : '미발송'}>
                    {r.email_sent ? (
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                    ) : (
                      <XCircle className="h-4 w-4 text-gray-300 dark:text-gray-600" />
                    )}
                  </div>
                  <div className="mt-1 text-right sm:mt-0">
                    <span className="text-xs text-gray-500 dark:text-gray-400" title={formatDate(r.created_at)}>
                      <Clock className="mr-1 inline h-3 w-3" />
                      {formatRelative(r.created_at)}
                    </span>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {page * PAGE_SIZE + 1}-{Math.min((page + 1) * PAGE_SIZE, total)} / {total}건
          </span>
          <div className="flex items-center gap-1">
            <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0}
              className="rounded-md p-1.5 text-gray-500 transition-colors hover:bg-gray-100 disabled:opacity-30 dark:hover:bg-gray-800">
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="px-2 text-xs text-gray-600 dark:text-gray-400">{page + 1} / {totalPages}</span>
            <button onClick={() => setPage(Math.min(totalPages - 1, page + 1))} disabled={page >= totalPages - 1}
              className="rounded-md p-1.5 text-gray-500 transition-colors hover:bg-gray-100 disabled:opacity-30 dark:hover:bg-gray-800">
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
