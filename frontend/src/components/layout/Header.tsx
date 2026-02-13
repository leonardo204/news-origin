import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Newspaper, TrendingUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTrackingStore } from '@/stores/useTrackingStore'

export default function Header() {
  const location = useLocation()
  const navigate = useNavigate()

  const navItems = [
    { to: '/', label: '추적', icon: Newspaper },
    { to: '/trends', label: '트렌드', icon: TrendingUp },
  ]

  const handleLogoClick = (e: React.MouseEvent) => {
    e.preventDefault()
    useTrackingStore.getState().reset()
    if (location.pathname === '/') {
      window.location.reload()
    } else {
      navigate('/')
    }
  }

  const handleHomeClick = () => {
    useTrackingStore.getState().reset()
  }

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-gray-950/80 backdrop-blur-sm" role="banner">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
        <a href="/" onClick={handleLogoClick} className="flex items-center gap-2 text-lg font-bold" aria-label="News Origin 홈으로 이동">
          <Newspaper className="h-5 w-5 text-lifecycle-origin" aria-hidden="true" />
          <span>
            News <span className="text-lifecycle-origin">Origin</span>
          </span>
        </a>

        <nav className="flex items-center gap-1" aria-label="주요 내비게이션">
          {navItems.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              onClick={to === '/' ? handleHomeClick : undefined}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors',
                location.pathname === to
                  ? 'bg-secondary text-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
              aria-current={location.pathname === to ? 'page' : undefined}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  )
}
