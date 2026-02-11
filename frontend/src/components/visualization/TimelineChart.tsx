import ReactECharts from 'echarts-for-react'
import { LIFECYCLE_COLORS, LIFECYCLE_LABELS, formatDate } from '@/lib/utils'
import type { TimelineItem, ExplosionPoint, LifecycleStage } from '@/types'

interface TimelineChartProps {
  items: TimelineItem[]
  explosions: ExplosionPoint[]
}

export default function TimelineChart({ items, explosions }: TimelineChartProps) {
  if (items.length === 0) {
    return (
      <div className="flex h-96 items-center justify-center text-muted-foreground">
        타임라인 데이터가 없습니다.
      </div>
    )
  }

  // Group items by lifecycle stage for scatter series
  const stages = ['origin', 'spread', 'explosion', 'sustained', 'fadeout', 'resurge', 'isolated'] as LifecycleStage[]
  const series = stages
    .map((stage) => {
      const stageItems = items.filter((item) => item.lifecycle_stage === stage)
      if (stageItems.length === 0) return null
      return {
        name: LIFECYCLE_LABELS[stage],
        type: 'scatter' as const,
        data: stageItems.map((item) => [
          item.published_at,
          item.similarity_score,
          item.title,
          item.publisher,
        ]),
        symbolSize: stage === 'origin' ? 18 : 12,
        itemStyle: {
          color: LIFECYCLE_COLORS[stage],
        },
      }
    })
    .filter(Boolean)

  // Add explosion zone markers
  const markAreas = explosions.map((exp) => [
    {
      xAxis: exp.start_time,
      itemStyle: {
        color: 'rgba(239, 68, 68, 0.08)',
        borderColor: 'rgba(239, 68, 68, 0.3)',
        borderWidth: 1,
        borderType: 'dashed' as const,
      },
    },
    { xAxis: exp.end_time },
  ])

  if (series.length > 0 && markAreas.length > 0) {
    (series[0] as Record<string, unknown>).markArea = { data: markAreas }
  }

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 12 },
      formatter: (params: { value: [string, number, string, string] }) => {
        const [time, score, title, publisher] = params.value
        return `
          <div style="max-width:300px">
            <div style="font-weight:600;margin-bottom:4px">${title}</div>
            <div style="color:#9ca3af;font-size:11px">${publisher || '알 수 없음'}</div>
            <div style="color:#9ca3af;font-size:11px;margin-top:4px">
              ${formatDate(time)} · 유사도 ${(score * 100).toFixed(1)}%
            </div>
          </div>`
      },
    },
    legend: {
      top: 8,
      textStyle: { color: '#9ca3af', fontSize: 11 },
      itemWidth: 10,
      itemHeight: 10,
    },
    grid: {
      left: 50,
      right: 30,
      top: 50,
      bottom: 40,
    },
    xAxis: {
      type: 'time',
      axisLine: { lineStyle: { color: '#374151' } },
      axisLabel: { color: '#9ca3af', fontSize: 10 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      name: '유사도',
      nameTextStyle: { color: '#9ca3af', fontSize: 11 },
      min: 0,
      max: 1,
      axisLine: { lineStyle: { color: '#374151' } },
      axisLabel: {
        color: '#9ca3af',
        fontSize: 10,
        formatter: (v: number) => `${(v * 100).toFixed(0)}%`,
      },
      splitLine: { lineStyle: { color: '#1f2937' } },
    },
    series,
  }

  return (
    <ReactECharts
      option={option}
      style={{ height: 500 }}
      theme="dark"
      notMerge
      opts={{ renderer: 'canvas' }}
    />
  )
}
