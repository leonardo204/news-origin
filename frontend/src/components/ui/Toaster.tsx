import { useEffect, useState } from 'react'
import { X, CheckCircle2, XCircle, AlertTriangle, Info } from 'lucide-react'
import { useToastStore, type Toast, type ToastType } from '@/stores/useToastStore'

const TOAST_CONFIG: Record<ToastType, { icon: React.ElementType; bgClass: string; iconClass: string }> = {
  success: {
    icon: CheckCircle2,
    bgClass: 'bg-green-500/10 border-green-500/30',
    iconClass: 'text-green-400',
  },
  error: {
    icon: XCircle,
    bgClass: 'bg-red-500/10 border-red-500/30',
    iconClass: 'text-red-400',
  },
  warning: {
    icon: AlertTriangle,
    bgClass: 'bg-amber-500/10 border-amber-500/30',
    iconClass: 'text-amber-400',
  },
  info: {
    icon: Info,
    bgClass: 'bg-blue-500/10 border-blue-500/30',
    iconClass: 'text-blue-400',
  },
}

function ToastItem({ toast }: { toast: Toast }) {
  const { removeToast } = useToastStore()
  const [progress, setProgress] = useState(100)
  const config = TOAST_CONFIG[toast.type]
  const Icon = config.icon

  useEffect(() => {
    if (!toast.duration || toast.duration <= 0) return

    const duration = toast.duration
    const startTime = Date.now()
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime
      const remaining = Math.max(0, 100 - (elapsed / duration) * 100)
      setProgress(remaining)

      if (remaining === 0) {
        clearInterval(interval)
      }
    }, 16) // ~60fps

    return () => clearInterval(interval)
  }, [toast.duration])

  return (
    <div
      className={`group relative flex w-80 items-start gap-3 rounded-lg border p-3 shadow-lg backdrop-blur-sm animate-in slide-in-from-right fade-in duration-300 ${config.bgClass}`}
      role="alert"
    >
      <Icon className={`h-5 w-5 shrink-0 ${config.iconClass}`} aria-hidden="true" />
      <p className="flex-1 text-sm leading-snug text-foreground">{toast.message}</p>
      <button
        onClick={() => removeToast(toast.id)}
        className="shrink-0 rounded p-0.5 text-muted-foreground transition-colors hover:bg-background/50 hover:text-foreground"
        aria-label="알림 닫기"
      >
        <X className="h-4 w-4" />
      </button>
      {toast.duration && toast.duration > 0 && (
        <div className="absolute bottom-0 left-0 right-0 h-1 overflow-hidden rounded-b-lg bg-background/20">
          <div
            className={`h-full transition-all duration-100 ease-linear ${config.iconClass.replace('text-', 'bg-')}`}
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  )
}

export default function Toaster() {
  const { toasts } = useToastStore()

  if (toasts.length === 0) return null

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2" aria-live="polite" aria-atomic="true">
      {toasts.map((toast) => (
        <div key={toast.id} className="pointer-events-auto">
          <ToastItem toast={toast} />
        </div>
      ))}
    </div>
  )
}
