import { create } from 'zustand'
import type {
  ArticleTrendsResponse,
  RecentArticleItem,
  StatsOverview,
} from '@/types'
import * as api from '@/services/api'

interface TrendState {
  // Article-based trends
  articleTrends: ArticleTrendsResponse | null
  recentArticles: RecentArticleItem[]
  expandedClusterId: string | null

  // Header 호환 (기존 유지)
  stats: StatsOverview | null

  // UI state
  isLoading: boolean
  error: string | null
  period: '24h' | '7d' | '30d'

  setPeriod: (period: '24h' | '7d' | '30d') => void
  toggleCluster: (clusterId: string) => void
  loadArticleTrends: () => Promise<void>
  loadRecentArticles: () => Promise<void>
  loadStats: () => Promise<void>
}

export const useTrendStore = create<TrendState>((set, get) => ({
  articleTrends: null,
  recentArticles: [],
  expandedClusterId: null,
  stats: null,
  isLoading: false,
  error: null,
  period: '24h',

  setPeriod: (period) => {
    set({ period })
    get().loadArticleTrends()
  },

  toggleCluster: (clusterId) => {
    set((state) => ({
      expandedClusterId: state.expandedClusterId === clusterId ? null : clusterId,
    }))
  },

  loadArticleTrends: async () => {
    set({ isLoading: true, error: null })
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
}))
