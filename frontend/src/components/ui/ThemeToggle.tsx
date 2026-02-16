import { Moon, Sun, Monitor } from 'lucide-react'
import { useTheme } from '@/hooks/useTheme'

const options = [
  { value: 'light' as const, icon: Sun, label: '라이트' },
  { value: 'dark' as const, icon: Moon, label: '다크' },
  { value: 'system' as const, icon: Monitor, label: '시스템' },
]

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  const cycle = () => {
    const order = ['light', 'dark', 'system'] as const
    const idx = order.indexOf(theme)
    setTheme(order[(idx + 1) % order.length])
  }

  const current = options.find((o) => o.value === theme) || options[1]
  const Icon = current.icon

  return (
    <button
      onClick={cycle}
      className="flex items-center justify-center rounded-md border border-border px-2 py-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
      aria-label={`테마: ${current.label}`}
      title={`현재: ${current.label} 모드`}
    >
      <Icon className="h-4 w-4" />
    </button>
  )
}
