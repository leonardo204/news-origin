import { onCLS, onLCP, onFCP, onTTFB, onINP } from 'web-vitals'

type Metric = { name: string; value: number; rating: string }

function reportMetric(metric: Metric) {
  if (import.meta.env.DEV) {
    console.log(`[Web Vitals] ${metric.name}: ${metric.value.toFixed(2)} (${metric.rating})`)
  } else {
    const body = JSON.stringify({ name: metric.name, value: metric.value, rating: metric.rating })
    if (navigator.sendBeacon) {
      navigator.sendBeacon('/api/health/vitals', new Blob([body], { type: 'application/json' }))
    } else {
      fetch('/api/health/vitals', { method: 'POST', body, headers: { 'Content-Type': 'application/json' }, keepalive: true }).catch(() => {})
    }
  }
}

export function initWebVitals() {
  onCLS(reportMetric)
  onLCP(reportMetric)
  onFCP(reportMetric)
  onTTFB(reportMetric)
  onINP(reportMetric)
}
