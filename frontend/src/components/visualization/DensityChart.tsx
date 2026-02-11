import ReactECharts from 'echarts-for-react'
import { formatDate } from '@/lib/utils'
import type { DensityPoint, ExplosionPoint } from '@/types'

interface DensityChartProps {
  density: DensityPoint[]
  explosions: ExplosionPoint[]
}

export default function DensityChart({ density, explosions }: DensityChartProps) {
  if (density.length === 0) {
    return (
      <div className="flex h-96 items-center justify-center text-muted-foreground">
        밀도 데이터가 없습니다.
      </div>
    )
  }

  const markAreas = explosions.map((exp) => [
    {
      xAxis: exp.start_time,
      itemStyle: {
        color: 'rgba(239, 68, 68, 0.1)',
      },
      label: {
        show: true,
        position: 'insideTop' as const,
        formatter: `폭발 (${exp.peak_count}건)`,
        color: '#ef4444',
        fontSize: 10,
      },
    },
    { xAxis: exp.end_time },
  ])

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 12 },
      formatter: (params: Array<{ value: [string, number] }>) => {
        const [time, count] = params[0].value
        return `${formatDate(time)}<br/>기사 수: <strong>${count}</strong>건`
      },
    },
    grid: {
      left: 50,
      right: 30,
      top: 30,
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
      name: '기사 수',
      nameTextStyle: { color: '#9ca3af', fontSize: 11 },
      axisLine: { lineStyle: { color: '#374151' } },
      axisLabel: { color: '#9ca3af', fontSize: 10 },
      splitLine: { lineStyle: { color: '#1f2937' } },
    },
    series: [
      {
        type: 'line',
        data: density.map((d) => [d.time, d.count]),
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: '#3b82f6',
          width: 2,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
              { offset: 1, color: 'rgba(59, 130, 246, 0.02)' },
            ],
          },
        },
        markArea: markAreas.length > 0 ? { data: markAreas } : undefined,
      },
    ],
  }

  return (
    <ReactECharts
      option={option}
      style={{ height: 400 }}
      theme="dark"
      notMerge
      opts={{ renderer: 'canvas' }}
    />
  )
}
