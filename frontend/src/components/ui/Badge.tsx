import { type HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'
import type { LifecycleStage } from '@/types'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  stage?: LifecycleStage
}

export function Badge({ stage, className, children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'lifecycle-badge',
        stage && `lifecycle-${stage}`,
        className,
      )}
      {...props}
    >
      {children}
    </span>
  )
}
