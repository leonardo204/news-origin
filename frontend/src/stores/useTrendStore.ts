import { create } from 'zustand'
import type {
  ArticleTrendsResponse,
  RecentArticleItem,
  StatsOverview,
  CrawlStatus,
} from '@/types'
import * as api from '@/services/api'

interface TrendState {
  // Article-based trends
  articleTrends: ArticleTrendsResponse | null
  recentArticles: RecentArticleItem[]
  expandedClusterId: string | null

  // Header 호환 (기존 유지)
  stats: StatsOverview | null

  // Crawl status
  crawlStatus: CrawlStatus

  // SSE connection status
  sseStatus: 'connected' | 'reconnecting' | 'offline'

  // UI state
  isLoading: boolean
  error: string | null
  period: '24h' | '7d' | '30d'
  trendView: 'overall' | 'category' | 'compare'

  setPeriod: (period: '24h' | '7d' | '30d') => void
  setTrendView: (view: 'overall' | 'category' | 'compare') => void
  toggleCluster: (clusterId: string) => void
  updateCrawlStatus: (status: CrawlStatus) => void
  setSseStatus: (status: 'connected' | 'reconnecting' | 'offline') => void
  loadArticleTrends: () => Promise<void>
  loadRecentArticles: () => Promise<void>
  loadStats: () => Promise<void>
  loadCrawlStatus: () => Promise<void>
}

export const useTrendStore = create<TrendState>((set, get) => ({
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

  setPeriod: (period) => {
    set({ period, articleTrends: null, isLoading: true })
    get().loadArticleTrends()
  },

  setTrendView: (view) => {
    set({ trendView: view })
  },

  toggleCluster: (clusterId) => {
    set((state) => ({
      expandedClusterId: state.expandedClusterId === clusterId ? null : clusterId,
    }))
  },

  updateCrawlStatus: (status) => {
    set({ crawlStatus: status })
  },

  setSseStatus: (status) => {
    set({ sseStatus: status })
  },

  loadArticleTrends: async () => {
    const hasData = !!get().articleTrends
    set({ isLoading: !hasData, error: null })
    try {
      const articleTrends = await api.getArticleTrends(get().period)
      set({ articleTrends, isLoading: false })
    } catch (err) {
      const message = err instanceof Error ? err.message : '트렌드를 불러올 수 없습니다.'
      set({ isLoading: false, error: message })
    }
  },

  loadRecentArticles: async () => {
    try {
      const recentArticles = await api.getRecentArticles(20)
      set({ recentArticles })
    } catch {
      // non-critical
    }
  },

  loadStats: async () => {
    try {
      const stats = await api.getStats()
      set({ stats })
    } catch {
      set({ stats: null })
    }
  },

  loadCrawlStatus: async () => {
    try {
      const crawlStatus = await api.getCrawlStatus()
      set({ crawlStatus })
    } catch {
      // non-critical — keep previous status
    }
  },
}))
