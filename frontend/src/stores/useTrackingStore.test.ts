import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useTrackingStore } from './useTrackingStore'

// Mock api module
vi.mock('@/services/api', () => ({
  trackArticle: vi.fn(),
  confirmTracking: vi.fn(),
  getTrackingStatus: vi.fn(),
  getTimeline: vi.fn(),
}))

// Mock toast
vi.mock('@/stores/useToastStore', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

import * as api from '@/services/api'

describe('useTrackingStore', () => {
  beforeEach(() => {
    useTrackingStore.getState().reset()
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts with default state', () => {
    const state = useTrackingStore.getState()
    expect(state.searchQuery).toBe('')
    expect(state.isSearching).toBe(false)
    expect(state.searchResult).toBeNull()
    expect(state.searchError).toBeNull()
    expect(state.trackingId).toBeNull()
    expect(state.timeline).toBeNull()
    expect(state.viewMode).toBe('timeline')
  })

  it('setSearchQuery updates query', () => {
    useTrackingStore.getState().setSearchQuery('test query')
    expect(useTrackingStore.getState().searchQuery).toBe('test query')
  })

  it('submitSearch sets loading state', async () => {
    const mockResult = { input_type: 'title' as const, article: null, candidates: [] }
    vi.mocked(api.trackArticle).mockResolvedValue(mockResult)

    useTrackingStore.getState().setSearchQuery('뉴스 검색')
    const promise = useTrackingStore.getState().submitSearch()

    expect(useTrackingStore.getState().isSearching).toBe(true)

    await promise
    expect(useTrackingStore.getState().isSearching).toBe(false)
    expect(useTrackingStore.getState().searchResult).toEqual(mockResult)
  })

  it('submitSearch handles error', async () => {
    vi.mocked(api.trackArticle).mockRejectedValue(new Error('네트워크 오류'))

    useTrackingStore.getState().setSearchQuery('test')
    await useTrackingStore.getState().submitSearch()

    expect(useTrackingStore.getState().isSearching).toBe(false)
    expect(useTrackingStore.getState().searchError).toBe('네트워크 오류')
  })

  it('submitSearch does nothing for empty query', async () => {
    useTrackingStore.getState().setSearchQuery('   ')
    await useTrackingStore.getState().submitSearch()

    expect(api.trackArticle).not.toHaveBeenCalled()
  })

  it('setViewMode changes view', () => {
    useTrackingStore.getState().setViewMode('timeline')
    expect(useTrackingStore.getState().viewMode).toBe('timeline')
  })

  it('reset clears all state', () => {
    // Set some state
    useTrackingStore.setState({
      searchQuery: 'test',
      isSearching: true,
      trackingId: 'abc-123',
      viewMode: 'density',
    })

    useTrackingStore.getState().reset()

    const state = useTrackingStore.getState()
    expect(state.searchQuery).toBe('')
    expect(state.isSearching).toBe(false)
    expect(state.trackingId).toBeNull()
    expect(state.viewMode).toBe('timeline')
  })

  it('reset clears poll timer', () => {
    const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout')

    // Simulate active timer
    const timer = setTimeout(() => {}, 1000)
    useTrackingStore.setState({ _pollTimer: timer })

    useTrackingStore.getState().reset()

    expect(clearTimeoutSpy).toHaveBeenCalledWith(timer)
    expect(useTrackingStore.getState()._pollTimer).toBeNull()
  })

  it('reset aborts in-flight request', () => {
    const controller = new AbortController()
    const abortSpy = vi.spyOn(controller, 'abort')
    useTrackingStore.setState({ _abortController: controller })

    useTrackingStore.getState().reset()

    expect(abortSpy).toHaveBeenCalled()
    expect(useTrackingStore.getState()._abortController).toBeNull()
  })
})
