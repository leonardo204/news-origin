/**
 * ECharts tree-shaking 최적화 설정
 *
 * echarts/core에서 필요한 컴포넌트만 import하여 번들 사이즈 최적화
 * 전체 echarts 패키지 대신 필요한 차트 타입과 컴포넌트만 등록
 */

import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  TitleComponent,
  LegendComponent,
  MarkAreaComponent,
  GraphicComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

// 필요한 컴포넌트만 등록
echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  TitleComponent,
  LegendComponent,
  MarkAreaComponent,
  GraphicComponent,
  DataZoomComponent,
  CanvasRenderer,
])

// 다크모드용 커스텀 테마 (투명 배경 + 다크 텍스트)
echarts.registerTheme('dark-transparent', {
  backgroundColor: 'transparent',
  textStyle: { color: '#9CA3AF' },
  title: { textStyle: { color: '#E5E7EB' } },
  legend: { textStyle: { color: '#9CA3AF' } },
  categoryAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#9CA3AF' },
    splitLine: { lineStyle: { color: 'rgba(55,65,81,0.3)' } },
  },
  valueAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#9CA3AF' },
    splitLine: { lineStyle: { color: 'rgba(55,65,81,0.3)' } },
  },
})

export default echarts
