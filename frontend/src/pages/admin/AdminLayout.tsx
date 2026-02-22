import { useState, useEffect } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useTheme } from '@/hooks/useTheme'
import { useAdminStore } from '@/stores/useAdminStore'
import {
  LayoutDashboard,
  Brain,
  Server,
  BarChart3,
  FileText,
  Settings2,
  LogOut,
  Sun,
  Moon,
  Menu,
  X,
  Newspaper,
  Monitor,
  Activity,
  Mail,
} from 'lucide-react'

interface NavItem {
  path: string
  label: string
  icon: typeof LayoutDashboard
  exact?: boolean
}

const navItems: NavItem[] = [
  { path: '/admin', label: '개요', icon: LayoutDashboard, exact: true },
  { path: '/admin/collection', label: '수집 통계', icon: BarChart3 },
  { path: '/admin/mlops', label: 'MLOps', icon: Brain },
  { path: '/admin/system', label: '시스템', icon: Server },
  { path: '/admin/traffic', label: '트래픽', icon: Activity },
  { path: '/admin/reports', label: '리포트', icon: Mail },
  { path: '/admin/logs', label: '로그', icon: FileText },
  { path: '/admin/settings', label: '설정', icon: Settings2 },
]

function isNavActive(itemPath: string, currentPath: string, exact?: boolean) {
  if (exact) return currentPath === itemPath
  return currentPath.startsWith(itemPath)
}

export default function AdminLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const { theme, setTheme, resolvedTheme } = useTheme()
  const { isAuthenticated, username, logout } = useAdminStore()

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/admin/login', { replace: true })
    }
  }, [isAuthenticated, navigate])

  const handleLogout = () => {
    logout()
    navigate('/admin/login')
  }

  const cycleTheme = () => {
    const order = ['light', 'dark', 'system'] as const
    const idx = order.indexOf(theme)
    setTheme(order[(idx + 1) % order.length])
  }

  const ThemeIcon = theme === 'system' ? Monitor : resolvedTheme === 'dark' ? Moon : Sun
  const themeLabel = theme === 'system' ? '시스템' : resolvedTheme === 'dark' ? '다크' : '라이트'

  // Get current page title
  const currentNav = navItems.find((item) =>
    isNavActive(item.path, location.pathname, item.exact)
  )
  const pageTitle = currentNav?.label || '관리자'

  // Close mobile sidebar on route change
  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  if (!isAuthenticated) return null

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50 dark:bg-gray-950">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-40 flex flex-col border-r border-gray-200 bg-white transition-all duration-200 dark:border-gray-800 dark:bg-gray-900
          lg:static lg:z-auto
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          ${collapsed ? 'w-16' : 'w-64'}
        `}
      >
        {/* Sidebar header */}
        <div
          className={`flex h-14 shrink-0 items-center border-b border-gray-200 dark:border-gray-800 ${
            collapsed ? 'justify-center px-2' : 'gap-3 px-4'
          }`}
        >
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-600">
            <Newspaper className="h-4 w-4 text-white" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <h2 className="truncate text-sm font-bold text-gray-900 dark:text-gray-100">
                News Origin
              </h2>
              <p className="truncate text-xs text-gray-500 dark:text-gray-500">Admin</p>
            </div>
          )}

          {/* Close button for mobile */}
          <button
            onClick={() => setSidebarOpen(false)}
            className="ml-auto rounded-md p-1 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 lg:hidden"
            aria-label="사이드바 닫기"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-2 py-3">
          <ul className="space-y-0.5">
            {navItems.map((item) => {
              const active = isNavActive(item.path, location.pathname, item.exact)
              const Icon = item.icon
              return (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    title={collapsed ? item.label : undefined}
                    className={`
                      flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors
                      ${collapsed ? 'justify-center' : ''}
                      ${
                        active
                          ? 'bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400'
                          : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200'
                      }
                    `}
                  >
                    <Icon className={`h-4 w-4 shrink-0 ${active ? 'text-blue-600 dark:text-blue-400' : ''}`} />
                    {!collapsed && <span className="truncate">{item.label}</span>}
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>

        {/* Sidebar footer: collapse toggle (desktop only) */}
        <div className="hidden shrink-0 border-t border-gray-200 p-2 dark:border-gray-800 lg:block">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="flex w-full items-center justify-center rounded-lg px-3 py-2 text-sm text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-500 dark:hover:bg-gray-800 dark:hover:text-gray-300"
            title={collapsed ? '사이드바 펼치기' : '사이드바 접기'}
          >
            <Menu className="h-4 w-4" />
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top header bar */}
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-gray-200 bg-white px-4 dark:border-gray-800 dark:bg-gray-900 lg:px-6">
          <div className="flex items-center gap-3">
            {/* Mobile hamburger */}
            <button
              onClick={() => setSidebarOpen(true)}
              className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 lg:hidden"
              aria-label="메뉴 열기"
            >
              <Menu className="h-5 w-5" />
            </button>
            <h1 className="text-base font-semibold text-gray-900 dark:text-gray-100">
              {pageTitle}
            </h1>
          </div>

          <div className="flex items-center gap-2">
            {/* Username badge */}
            {username && (
              <span className="hidden text-sm text-gray-500 dark:text-gray-400 sm:inline">
                {username}
              </span>
            )}

            {/* Theme toggle */}
            <button
              onClick={cycleTheme}
              className="rounded-lg p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
              aria-label={`테마: ${themeLabel}`}
              title={`현재: ${themeLabel} 모드`}
            >
              <ThemeIcon className="h-4 w-4" />
            </button>

            {/* Logout */}
            <button
              onClick={handleLogout}
              className="rounded-lg p-2 text-gray-500 transition-colors hover:bg-red-50 hover:text-red-600 dark:text-gray-400 dark:hover:bg-red-500/10 dark:hover:text-red-400"
              aria-label="로그아웃"
              title="로그아웃"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
