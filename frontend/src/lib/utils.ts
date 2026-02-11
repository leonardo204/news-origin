import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { LifecycleStage, SimilarityCategory } from '@/types'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const LIFECYCLE_COLORS: Record<LifecycleStage, string> = {
  origin: '#22c55e',
  spread: '#3b82f6',
  explosion: '#ef4444',
  sustained: '#f59e0b',
  fadeout: '#6b7280',
  resurge: '#a855f7',
  isolated: '#14b8a6',
}

export const LIFECYCLE_LABELS: Record<LifecycleStage, string> = {
  origin: '기원',
  spread: '확산',
  explosion: '폭발',
  sustained: '지속',
  fadeout: '소멸',
  resurge: '재부상',
  isolated: '고립',
}

export const SIMILARITY_LABELS: Record<SimilarityCategory, string> = {
  same: '동일 기사',
  derivative: '파생 기사',
  related: '관련 기사',
  isolated: '고립 기사',
}

export function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  if (diffMin < 1) return '방금 전'
  if (diffMin < 60) return `${diffMin}분 전`
  if (diffHour < 24) return `${diffHour}시간 전`
  if (diffDay < 7) return `${diffDay}일 전`
  return formatDate(dateStr)
}

export function formatDuration(hours: number | null): string {
  if (hours === null) return '-'
  if (hours < 1) return `${Math.round(hours * 60)}분`
  if (hours < 24) return `${Math.round(hours)}시간`
  const days = Math.floor(hours / 24)
  const remainHours = Math.round(hours % 24)
  return remainHours > 0 ? `${days}일 ${remainHours}시간` : `${days}일`
}

export function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str
  return str.slice(0, maxLen) + '...'
}
