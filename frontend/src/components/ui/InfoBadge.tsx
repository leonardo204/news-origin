import * as Tooltip from '@radix-ui/react-tooltip'
import { HelpCircle } from 'lucide-react'

interface InfoBadgeProps {
  content: string
  side?: 'top' | 'bottom' | 'left' | 'right'
}

export default function InfoBadge({ content, side = 'bottom' }: InfoBadgeProps) {
  const lines = content.split('\n')

  return (
    <Tooltip.Provider delayDuration={200}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button
            type="button"
            className="inline-flex items-center justify-center rounded-full text-gray-400 hover:text-gray-600 focus:outline-none dark:text-gray-500 dark:hover:text-gray-300"
            aria-label="도움말"
          >
            <HelpCircle className="h-3.5 w-3.5" />
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            side={side}
            sideOffset={6}
            className="z-50 max-w-xs rounded-lg bg-gray-900 px-3 py-2.5 text-xs leading-relaxed text-gray-100 shadow-lg dark:bg-gray-800 dark:text-gray-200"
          >
            {lines.map((line, i) => (
              <p key={i} className={i > 0 ? 'mt-1.5' : ''}>
                {line}
              </p>
            ))}
            <Tooltip.Arrow className="fill-gray-900 dark:fill-gray-800" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}
