import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useTrendStore } from './useTrendStore'

vi.mock('@/services/api', () => ({
  getHotTrends: vi.fn(),
  getPopularSearches: vi.fn(),
  getStats: vi.fn(),
}))

import * as api from '@/services/api'

describe('useTrendStore', () => {
  beforeEach(() => {
    useTrendStore.setState({
      trends: [],
      popularSearches: [],
      stats: null,
      isLoading: false,
      error: null,
      period: '24h',
    })
    vi.clearAllMocks()
  })

  it('starts with default state', () => {
    const state = useTrendStore.getState()
    expect(state.trends).toEqual([])
    expect(state.popularSearches).toEqual([])
    expect(state.stats).toBeNull()
    expect(state.isLoading).toBe(false)
    expect(state.error).toBeNull()
    expect(state.period).toBe('24h')
  })

  it('setPeriod updates period and triggers loadTrends', async () => {
    vi.mocked(api.getHotTrends).mockResolvedValue([])
    vi.mocked(api.getPopularSearches).mockResolvedValue([])

    useTrendStore.getState().setPeriod('7d')

    expect(useTrendStore.getState().period).toBe('7d')
    // loadTrends was called
    expect(api.getHotTrends).toHaveBeenCalledWith('7d')
  })

  it('loadTrends fetches trends and popular searches', async () => {
    const mockTrends = [{ title: '테스트', tracking_count: 5, latest_tracking_id: 'abc-123', last_tracked_at: '2024-01-15T10:00:00Z' }]
    const mockSearches = [{ query: '검색어', count: 3 }]

    vi.mocked(api.getHotTrends).mockResolvedValue(mockTrends)
    vi.mocked(api.getPopularSearches).mockResolvedValue(mockSearches)

    await useTrendStore.getState().loadTrends()

    const state = useTrendStore.getState()
    expect(state.trends).toEqual(mockTrends)
    expect(state.popularSearches).toEqual(mockSearches)
    expect(state.isLoading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('loadTrends sets loading state', async () => {
    vi.mocked(api.getHotTrends).mockResolvedValue([])
    vi.mocked(api.getPopularSearches).mockResolvedValue([])

    const promise = useTrendStore.getState().loadTrends()
    expect(useTrendStore.getState().isLoading).toBe(true)

    await promise
    expect(useTrendStore.getState().isLoading).toBe(false)
  })

  it('loadTrends handles error', async () => {
    vi.mocked(api.getHotTrends).mockRejectedValue(new Error('네트워크 오류'))
    vi.mocked(api.getPopularSearches).mockResolvedValue([])

    await useTrendStore.getState().loadTrends()

    const state = useTrendStore.getState()
    expect(state.isLoading).toBe(false)
    expect(state.error).toBe('네트워크 오류')
  })

  it('loadTrends uses generic message for non-Error', async () => {
    vi.mocked(api.getHotTrends).mockRejectedValue('unknown')
    vi.mocked(api.getPopularSearches).mockResolvedValue([])

    await useTrendStore.getState().loadTrends()

    expect(useTrendStore.getState().error).toBe('트렌드를 불러올 수 없습니다.')
  })

  it('loadStats sets stats on success', async () => {
    const mockStats = { total_trackings: 10, total_articles: 50, active_trackings: 2, embedded_articles: 45, recent_articles_24h: 12, last_crawl_at: null, category_counts: {} }
    vi.mocked(api.getStats).mockResolvedValue(mockStats)

    await useTrendStore.getState().loadStats()

    expect(useTrendStore.getState().stats).toEqual(mockStats)
  })

  it('loadStats clears stats on failure silently', async () => {
    useTrendStore.setState({ stats: { total_trackings: 10, total_articles: 50, active_trackings: 2, embedded_articles: 45, recent_articles_24h: 12, last_crawl_at: null, category_counts: {} } })
    vi.mocked(api.getStats).mockRejectedValue(new Error('서버 오류'))

    await useTrendStore.getState().loadStats()

    expect(useTrendStore.getState().stats).toBeNull()
    // error should NOT be set (non-critical)
    expect(useTrendStore.getState().error).toBeNull()
  })
})
