import { create } from 'zustand'
import type { TrendItem, PopularSearch, StatsOverview } from '@/types'
import * as api from '@/services/api'

interface TrendState {
  trends: TrendItem[]
  popularSearches: PopularSearch[]
  stats: StatsOverview | null
  isLoading: boolean
  error: string | null
  period: '24h' | '7d' | '30d'

  setPeriod: (period: '24h' | '7d' | '30d') => void
  loadTrends: () => Promise<void>
  loadStats: () => Promise<void>
}

export const useTrendStore = create<TrendState>((set, get) => ({
  trends: [],
  popularSearches: [],
  stats: null,
  isLoading: false,
  error: null,
  period: '24h',

  setPeriod: (period) => {
    set({ period })
    get().loadTrends()
  },

  loadTrends: async () => {
    set({ isLoading: true, error: null })
    try {
      const [trends, popularSearches] = await Promise.all([
        api.getHotTrends(get().period),
        api.getPopularSearches(),
      ])
      set({ trends, popularSearches, isLoading: false })
    } catch (err) {
      const message = err instanceof Error ? err.message : '트렌드를 불러올 수 없습니다.'
      set({ isLoading: false, error: message })
    }
  },

  loadStats: async () => {
    try {
      const stats = await api.getStats()
      set({ stats })
    } catch {
      // Stats failure is non-critical, don't set error
      set({ stats: null })
    }
  },
}))
