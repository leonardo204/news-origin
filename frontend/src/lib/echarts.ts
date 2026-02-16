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
  CanvasRenderer,
])

export default echarts
