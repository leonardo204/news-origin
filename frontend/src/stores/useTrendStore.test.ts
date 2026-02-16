import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useTrendStore } from './useTrendStore'

vi.mock('@/services/api', () => ({
  getArticleTrends: vi.fn(),
  getRecentArticles: vi.fn(),
  getStats: vi.fn(),
  getCrawlStatus: vi.fn(),
}))

import * as api from '@/services/api'

describe('useTrendStore', () => {
  beforeEach(() => {
    useTrendStore.setState({
      articleTrends: null,
      recentArticles: [],
      expandedClusterId: null,
      stats: null,
      crawlStatus: { phase: 'idle', started_at: null, detail: null },
      sseStatus: 'connected',
      isLoading: false,
      error: null,
      period: '24h',
      trendView: 'overall',
    })
    vi.clearAllMocks()
  })

  it('starts with default state', () => {
    const state = useTrendStore.getState()
    expect(state.articleTrends).toBeNull()
    expect(state.recentArticles).toEqual([])
    expect(state.stats).toBeNull()
    expect(state.crawlStatus.phase).toBe('idle')
    expect(state.sseStatus).toBe('connected')
    expect(state.isLoading).toBe(false)
    expect(state.error).toBeNull()
    expect(state.period).toBe('24h')
    expect(state.trendView).toBe('overall')
  })

  it('setPeriod updates period and triggers loadArticleTrends', async () => {
    const mockResponse = { clusters: [], total_articles: 0, total_clusters: 0, period: '7d', generated_at: '', category_distribution: {}, publisher_distribution: {}, hourly_counts: [] }
    vi.mocked(api.getArticleTrends).mockResolvedValue(mockResponse)

    useTrendStore.getState().setPeriod('7d')

    expect(useTrendStore.getState().period).toBe('7d')
    expect(api.getArticleTrends).toHaveBeenCalledWith('7d')
  })

  it('loadArticleTrends fetches article trends', async () => {
    const mockResponse = { clusters: [], total_articles: 10, total_clusters: 2, period: '24h', generated_at: '2024-01-15T10:00:00Z', category_distribution: {}, publisher_distribution: {}, hourly_counts: [] }
    vi.mocked(api.getArticleTrends).mockResolvedValue(mockResponse)

    await useTrendStore.getState().loadArticleTrends()

    const state = useTrendStore.getState()
    expect(state.articleTrends).toEqual(mockResponse)
    expect(state.isLoading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('loadArticleTrends sets loading state', async () => {
    const mockResponse = { clusters: [], total_articles: 0, total_clusters: 0, period: '24h', generated_at: '', category_distribution: {}, publisher_distribution: {}, hourly_counts: [] }
    vi.mocked(api.getArticleTrends).mockResolvedValue(mockResponse)

    const promise = useTrendStore.getState().loadArticleTrends()
    expect(useTrendStore.getState().isLoading).toBe(true)

    await promise
    expect(useTrendStore.getState().isLoading).toBe(false)
  })

  it('loadArticleTrends handles error', async () => {
    vi.mocked(api.getArticleTrends).mockRejectedValue(new Error('네트워크 오류'))

    await useTrendStore.getState().loadArticleTrends()

    const state = useTrendStore.getState()
    expect(state.isLoading).toBe(false)
    expect(state.error).toBe('네트워크 오류')
  })

  it('loadArticleTrends uses generic message for non-Error', async () => {
    vi.mocked(api.getArticleTrends).mockRejectedValue('unknown')

    await useTrendStore.getState().loadArticleTrends()

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

  it('toggleCluster expands and collapses cluster', () => {
    useTrendStore.getState().toggleCluster('abc-123')
    expect(useTrendStore.getState().expandedClusterId).toBe('abc-123')

    useTrendStore.getState().toggleCluster('abc-123')
    expect(useTrendStore.getState().expandedClusterId).toBeNull()
  })

  it('setTrendView updates view mode', () => {
    useTrendStore.getState().setTrendView('category')
    expect(useTrendStore.getState().trendView).toBe('category')

    useTrendStore.getState().setTrendView('overall')
    expect(useTrendStore.getState().trendView).toBe('overall')
  })

  it('setSseStatus updates connection status', () => {
    useTrendStore.getState().setSseStatus('reconnecting')
    expect(useTrendStore.getState().sseStatus).toBe('reconnecting')

    useTrendStore.getState().setSseStatus('offline')
    expect(useTrendStore.getState().sseStatus).toBe('offline')

    useTrendStore.getState().setSseStatus('connected')
    expect(useTrendStore.getState().sseStatus).toBe('connected')
  })

  it('updateCrawlStatus updates crawl status', () => {
    useTrendStore.getState().updateCrawlStatus({
      phase: 'crawling',
      started_at: '2026-01-01T00:00:00Z',
      detail: '10건 크롤링중',
    })

    const status = useTrendStore.getState().crawlStatus
    expect(status.phase).toBe('crawling')
    expect(status.started_at).toBe('2026-01-01T00:00:00Z')
    expect(status.detail).toBe('10건 크롤링중')
  })

  it('loadCrawlStatus fetches crawl status', async () => {
    const mockStatus = { phase: 'embedding' as const, started_at: '2026-01-01', detail: '임베딩 생성중' }
    vi.mocked(api.getCrawlStatus).mockResolvedValue(mockStatus)

    await useTrendStore.getState().loadCrawlStatus()

    expect(useTrendStore.getState().crawlStatus).toEqual(mockStatus)
  })

  it('loadCrawlStatus handles error silently', async () => {
    const previousStatus = { phase: 'idle' as const, started_at: null, detail: null }
    useTrendStore.setState({ crawlStatus: previousStatus })

    vi.mocked(api.getCrawlStatus).mockRejectedValue(new Error('서버 오류'))

    await useTrendStore.getState().loadCrawlStatus()

    // Should keep previous status on error
    expect(useTrendStore.getState().crawlStatus).toEqual(previousStatus)
  })

  it('loadRecentArticles fetches recent articles', async () => {
    const mockArticles = [
      { id: '1', title: '기사 1', publisher: '언론사1', published_at: '2026-01-01', created_at: '2026-01-01T00:00:00Z', url: 'https://example.com/1', category: 'politics' },
      { id: '2', title: '기사 2', publisher: '언론사2', published_at: '2026-01-02', created_at: '2026-01-02T00:00:00Z', url: 'https://example.com/2', category: 'economy' },
    ]
    vi.mocked(api.getRecentArticles).mockResolvedValue(mockArticles)

    await useTrendStore.getState().loadRecentArticles()

    expect(useTrendStore.getState().recentArticles).toEqual(mockArticles)
    expect(api.getRecentArticles).toHaveBeenCalledWith(20)
  })

  it('loadRecentArticles handles error silently', async () => {
    useTrendStore.setState({ recentArticles: [] })
    vi.mocked(api.getRecentArticles).mockRejectedValue(new Error('서버 오류'))

    await useTrendStore.getState().loadRecentArticles()

    // Should keep empty array on error (non-critical)
    expect(useTrendStore.getState().recentArticles).toEqual([])
  })
})
