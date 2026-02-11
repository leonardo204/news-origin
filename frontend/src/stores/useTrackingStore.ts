import { create } from 'zustand'
import type {
  TrackResponse,
  TrackingStatus,
  TimelineResponse,
  ViewMode,
} from '@/types'
import * as api from '@/services/api'
import { toast } from '@/stores/useToastStore'

interface TrackingState {
  // Search
  searchQuery: string
  isSearching: boolean
  searchResult: TrackResponse | null
  searchError: string | null

  // Tracking
  trackingId: string | null
  trackingStatus: TrackingStatus | null
  isPolling: boolean
  pollFailCount: number

  // Timeline data
  timeline: TimelineResponse | null
  isLoadingTimeline: boolean

  // View
  viewMode: ViewMode

  // Internal
  _pollTimer: ReturnType<typeof setTimeout> | null
  _abortController: AbortController | null

  // Actions
  setSearchQuery: (query: string) => void
  submitSearch: () => Promise<void>
  selectCandidate: (url: string) => Promise<void>
  confirmArticle: (articleId: string) => Promise<void>
  pollStatus: () => Promise<void>
  loadTimeline: (trackingId: string) => Promise<void>
  setViewMode: (mode: ViewMode) => void
  reset: () => void
}

export const useTrackingStore = create<TrackingState>((set, get) => ({
  searchQuery: '',
  isSearching: false,
  searchResult: null,
  searchError: null,
  trackingId: null,
  trackingStatus: null,
  isPolling: false,
  pollFailCount: 0,
  timeline: null,
  isLoadingTimeline: false,
  viewMode: 'graph',
  _pollTimer: null,
  _abortController: null,

  setSearchQuery: (query) => set({ searchQuery: query }),

  submitSearch: async () => {
    const { searchQuery } = get()
    if (!searchQuery.trim()) return

    set({ isSearching: true, searchError: null, searchResult: null })
    try {
      const result = await api.trackArticle({ text: searchQuery.trim() })
      set({ searchResult: result, isSearching: false })
    } catch (err) {
      const message = err instanceof Error ? err.message : '검색 중 오류가 발생했습니다.'
      set({ searchError: message, isSearching: false })
    }
  },

  selectCandidate: async (url) => {
    set({ isSearching: true, searchError: null })
    try {
      const result = await api.trackArticle({ text: url })
      if (result.article) {
        set({ searchResult: result, isSearching: false })
        // Auto-confirm: start tracking immediately
        get().confirmArticle(result.article.id)
      } else {
        set({ searchError: '기사를 가져올 수 없습니다.', isSearching: false })
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '기사를 가져오는 중 오류가 발생했습니다.'
      set({ searchError: message, isSearching: false })
    }
  },

  confirmArticle: async (articleId) => {
    try {
      const result = await api.confirmTracking({ article_id: articleId })
      set({
        trackingId: result.tracking_id,
        trackingStatus: {
          tracking_id: result.tracking_id,
          status: 'pending',
          progress: 0,
          total_articles: 0,
          message: result.message,
        },
        isPolling: true,
      })
      toast.info('기사 전파 분석을 시작합니다.')
      // Start polling
      get().pollStatus()
    } catch (err) {
      const message = err instanceof Error ? err.message : '추적 시작 중 오류가 발생했습니다.'
      set({ searchError: message })
      toast.error(message)
    }
  },

  pollStatus: async () => {
    const { trackingId, pollFailCount, isPolling } = get()
    if (!trackingId || !isPolling) return

    // Cancel previous in-flight poll request
    const prev = get()._abortController
    if (prev) prev.abort()

    const controller = new AbortController()
    set({ _abortController: controller })

    try {
      const status = await api.getTrackingStatus(trackingId, controller.signal)
      set({ trackingStatus: status, pollFailCount: 0 })

      if (status.status === 'completed') {
        set({ isPolling: false, _abortController: null })
        toast.success(`분석 완료! ${status.total_articles}개 기사를 발견했습니다.`)
        get().loadTimeline(trackingId)
      } else if (status.status === 'failed' || status.status === 'error') {
        set({ isPolling: false, _abortController: null, searchError: status.message || '분석에 실패했습니다.' })
        toast.error(status.message || '분석에 실패했습니다.')
      } else {
        const timer = setTimeout(() => get().pollStatus(), 2000)
        set({ _pollTimer: timer })
      }
    } catch (err) {
      // Don't count aborted requests as failures
      if (err instanceof Error && err.message === '요청이 취소되었습니다.') return

      const nextFail = pollFailCount + 1
      if (nextFail >= 5) {
        set({ isPolling: false, pollFailCount: 0, _abortController: null, searchError: '상태 확인에 실패했습니다. 잠시 후 다시 시도해주세요.' })
        toast.error('상태 확인에 실패했습니다.')
      } else {
        const delay = Math.min(2000 * Math.pow(1.5, nextFail), 10000)
        set({ pollFailCount: nextFail })
        const timer = setTimeout(() => get().pollStatus(), delay)
        set({ _pollTimer: timer })
      }
    }
  },

  loadTimeline: async (trackingId) => {
    set({ isLoadingTimeline: true })
    try {
      const timeline = await api.getTimeline(trackingId)
      set({ timeline, isLoadingTimeline: false, trackingId })
    } catch {
      set({ isLoadingTimeline: false, searchError: '타임라인 로드 중 오류가 발생했습니다.' })
    }
  },

  setViewMode: (mode) => set({ viewMode: mode }),

  reset: () => {
    // Clean up poll timer and abort controller
    const { _pollTimer, _abortController } = get()
    if (_pollTimer) clearTimeout(_pollTimer)
    if (_abortController) _abortController.abort()

    set({
      searchQuery: '',
      isSearching: false,
      searchResult: null,
      searchError: null,
      trackingId: null,
      trackingStatus: null,
      isPolling: false,
      pollFailCount: 0,
      timeline: null,
      isLoadingTimeline: false,
      viewMode: 'graph',
      _pollTimer: null,
      _abortController: null,
    })
  },
}))
