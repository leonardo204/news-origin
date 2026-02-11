import { describe, it, expect } from 'vitest'
import { cn, formatDate, formatRelativeTime, formatDuration, truncate } from './utils'

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar')
  })

  it('handles conditional classes', () => {
    expect(cn('base', false && 'hidden', 'visible')).toBe('base visible')
  })

  it('merges tailwind conflicts', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4')
  })
})

describe('formatDate', () => {
  it('returns dash for null', () => {
    expect(formatDate(null)).toBe('-')
  })

  it('formats a date string in Korean locale', () => {
    const result = formatDate('2024-01-15T10:30:00Z')
    expect(result).toContain('2024')
    expect(result).toContain('1')
    expect(result).toContain('15')
  })
})

describe('formatRelativeTime', () => {
  it('returns 방금 전 for very recent', () => {
    const now = new Date().toISOString()
    expect(formatRelativeTime(now)).toBe('방금 전')
  })

  it('returns minutes for recent times', () => {
    const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString()
    expect(formatRelativeTime(fiveMinAgo)).toBe('5분 전')
  })

  it('returns hours for older times', () => {
    const threeHoursAgo = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString()
    expect(formatRelativeTime(threeHoursAgo)).toBe('3시간 전')
  })

  it('returns days for much older times', () => {
    const twoDaysAgo = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString()
    expect(formatRelativeTime(twoDaysAgo)).toBe('2일 전')
  })
})

describe('formatDuration', () => {
  it('returns dash for null', () => {
    expect(formatDuration(null)).toBe('-')
  })

  it('formats minutes for less than 1 hour', () => {
    expect(formatDuration(0.5)).toBe('30분')
  })

  it('formats hours', () => {
    expect(formatDuration(5)).toBe('5시간')
  })

  it('formats days and hours', () => {
    expect(formatDuration(27)).toBe('1일 3시간')
  })

  it('formats whole days', () => {
    expect(formatDuration(48)).toBe('2일')
  })
})

describe('truncate', () => {
  it('returns original if shorter than max', () => {
    expect(truncate('hello', 10)).toBe('hello')
  })

  it('truncates and adds ellipsis', () => {
    expect(truncate('hello world', 5)).toBe('hello...')
  })

  it('handles exact length', () => {
    expect(truncate('hello', 5)).toBe('hello')
  })
})
