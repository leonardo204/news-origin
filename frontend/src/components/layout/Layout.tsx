import { Outlet } from 'react-router-dom'
import Header from './Header'

export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1" role="main">
        <Outlet />
      </main>
      <footer className="border-t border-border py-4 text-center text-sm text-muted-foreground" role="contentinfo">
        <p>News Origin &copy; {new Date().getFullYear()} &mdash; 뉴스의 기원을 추적합니다</p>
      </footer>
    </div>
  )
}
