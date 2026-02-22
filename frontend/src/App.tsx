import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { Skeleton } from '@/components/ui/Skeleton'
import { Card, CardContent } from '@/components/ui/Card'
import Layout from '@/components/layout/Layout'
import HomePage from '@/pages/HomePage'
import NotFoundPage from '@/pages/NotFoundPage'
import NetworkStatus from '@/components/ui/NetworkStatus'

// 배포 후 chunk 해시 변경 시 old chunk 요청 → 404 대응: 자동 새로고침
function lazyWithReload(factory: () => Promise<{ default: React.ComponentType }>) {
  return lazy(() =>
    factory().catch(() => {
      window.location.reload()
      return new Promise(() => {}) // 리로드 중 렌더 방지
    })
  )
}

// Lazy-load heavy pages (contain ECharts / G6)
const TimelinePage = lazyWithReload(() => import('@/pages/TimelinePage'))
const TrendsPage = lazyWithReload(() => import('@/pages/TrendsPage'))
const PolicyPage = lazyWithReload(() => import('@/pages/PolicyPage'))

// Lazy-load admin pages
const AdminLayout = lazyWithReload(() => import('@/pages/admin/AdminLayout'))
const LoginPage = lazyWithReload(() => import('@/pages/admin/LoginPage'))
const AdminOverview = lazyWithReload(() => import('@/pages/admin/OverviewPage'))
const AdminCollectionStats = lazyWithReload(() => import('@/pages/admin/CollectionStatsPage'))
const AdminMLOps = lazyWithReload(() => import('@/pages/admin/MLOpsPage'))
const AdminSystem = lazyWithReload(() => import('@/pages/admin/SystemPage'))
const AdminLogs = lazyWithReload(() => import('@/pages/admin/LogsPage'))
const AdminSettings = lazyWithReload(() => import('@/pages/admin/SettingsPage'))
const AdminTraffic = lazyWithReload(() => import('@/pages/admin/TrafficPage'))
const AdminReports = lazyWithReload(() => import('@/pages/admin/ReportsPage'))

function TimelinePageFallback() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-6">
        <Skeleton className="mb-2 h-3 w-12" />
        <Skeleton className="mb-3 h-7 w-2/3" />
        <div className="flex gap-3">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-32" />
        </div>
      </div>
      <Card>
        <CardContent className="p-4">
          <Skeleton className="h-96 w-full" />
        </CardContent>
      </Card>
    </div>
  )
}

function TrendsPageFallback() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-8 flex items-center justify-between">
        <Skeleton className="h-8 w-28" />
        <Skeleton className="h-9 w-40 rounded-lg" />
      </div>
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Card key={i}>
            <CardContent className="flex items-center gap-3 p-4">
              <Skeleton className="h-8 w-8 rounded" />
              <div className="space-y-1">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-8 w-20" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

export default function App() {
  return (
    <>
      <NetworkStatus />
      <ErrorBoundary>
      <Routes>
        {/* Admin routes — outside public Layout */}
        <Route path="/admin/login" element={<Suspense fallback={<div />}><LoginPage /></Suspense>} />
        <Route path="/admin" element={<Suspense fallback={<div />}><AdminLayout /></Suspense>}>
          <Route index element={<Suspense fallback={<div />}><AdminOverview /></Suspense>} />
          <Route path="collection" element={<Suspense fallback={<div />}><AdminCollectionStats /></Suspense>} />
          <Route path="mlops" element={<Suspense fallback={<div />}><AdminMLOps /></Suspense>} />
          <Route path="system" element={<Suspense fallback={<div />}><AdminSystem /></Suspense>} />
          <Route path="traffic" element={<Suspense fallback={<div />}><AdminTraffic /></Suspense>} />
          <Route path="reports" element={<Suspense fallback={<div />}><AdminReports /></Suspense>} />
          <Route path="logs" element={<Suspense fallback={<div />}><AdminLogs /></Suspense>} />
          <Route path="settings" element={<Suspense fallback={<div />}><AdminSettings /></Suspense>} />
        </Route>

        {/* Public routes */}
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route
            path="/timeline/:trackingId"
            element={
              <Suspense fallback={<TimelinePageFallback />}>
                <TimelinePage />
              </Suspense>
            }
          />
          <Route
            path="/trends"
            element={
              <Suspense fallback={<TrendsPageFallback />}>
                <TrendsPage />
              </Suspense>
            }
          />
          <Route
            path="/policy"
            element={
              <Suspense fallback={<div />}>
                <PolicyPage />
              </Suspense>
            }
          />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </ErrorBoundary>
    </>
  )
}
