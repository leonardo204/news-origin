import { GitBranch, Clock, BarChart3 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTrackingStore } from '@/stores/useTrackingStore'
import type { ViewMode } from '@/types'

const views: { mode: ViewMode; label: string; icon: typeof GitBranch }[] = [
  { mode: 'graph', label: '전파 그래프', icon: GitBranch },
  { mode: 'timeline', label: '타임라인', icon: Clock },
  { mode: 'density', label: '밀도 분석', icon: BarChart3 },
]

export default function ViewToggle() {
  const { viewMode, setViewMode } = useTrackingStore()

  return (
    <div className="inline-flex items-center rounded-lg border border-border bg-secondary/50 p-1">
      {views.map(({ mode, label, icon: Icon }) => (
        <button
          key={mode}
          onClick={() => setViewMode(mode)}
          className={cn(
            'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
            viewMode === mode
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <Icon className="h-3.5 w-3.5" />
          {label}
        </button>
      ))}
    </div>
  )
}
