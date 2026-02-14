export const CATEGORY_KEYS = [
  'headlines',
  'politics',
  'economy',
  'society',
  'tech',
  'entertainment',
] as const

export type CategoryKey = (typeof CATEGORY_KEYS)[number]

export const CATEGORY_LABELS: Record<string, string> = {
  headlines: '헤드라인',
  politics: '정치',
  economy: '경제',
  society: '사회',
  tech: 'IT/과학',
  entertainment: '연예/문화',
}

export const CATEGORY_COLORS: Record<string, string> = {
  headlines: '#10b981',
  politics: '#3b82f6',
  economy: '#f59e0b',
  society: '#f43f5e',
  tech: '#8b5cf6',
  entertainment: '#06b6d4',
}

export const CATEGORY_BG: Record<string, string> = {
  headlines: 'bg-emerald-400/15 text-emerald-400',
  politics: 'bg-blue-400/15 text-blue-400',
  economy: 'bg-amber-400/15 text-amber-400',
  society: 'bg-rose-400/15 text-rose-400',
  tech: 'bg-violet-400/15 text-violet-400',
  entertainment: 'bg-cyan-400/15 text-cyan-400',
}
