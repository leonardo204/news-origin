import axios, { type AxiosError } from 'axios'
import type {
  TrackInput,
  TrackResponse,
  ConfirmInput,
  ConfirmResponse,
  TrackingStatus,
  TimelineResponse,
  Article,
  TrendItem,
  PopularSearch,
  StatsOverview,
  TrackCandidate,
  ArticleTrendsResponse,
  RecentArticleItem,
  CrawlStatus,
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Retry config
const RETRY_STATUS_CODES = new Set([502, 503, 504])
const MAX_RETRIES = 2
const RETRY_DELAY = 1000

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// Response interceptor with retry for transient failures
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config
    if (!config) return Promise.reject(formatError(error))

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const configAny = config as any
    const retryCount: number = configAny.__retryCount || 0

    // Retry on 502/503/504 or network error (not timeout), GET only (POST는 중복 생성 방지)
    const isRetryable =
      config.method?.toUpperCase() !== 'POST' &&
      ((error.response && RETRY_STATUS_CODES.has(error.response.status)) ||
      (!error.response && error.code !== 'ECONNABORTED' && error.code !== 'ERR_CANCELED'))

    if (isRetryable && retryCount < MAX_RETRIES) {
      configAny.__retryCount = retryCount + 1
      await sleep(RETRY_DELAY * (retryCount + 1))
      return api(config)
    }

    return Promise.reject(formatError(error))
  },
)

function formatError(error: AxiosError): Error {
  if (error.code === 'ERR_CANCELED') {
    return new Error('요청이 취소되었습니다.')
  }
  if (error.response) {
    const detail = (error.response.data as Record<string, unknown>)?.detail
    const message = typeof detail === 'string' ? detail : '서버 오류가 발생했습니다.'
    return new Error(message)
  }
  if (error.code === 'ECONNABORTED') {
    return new Error('요청 시간이 초과되었습니다.')
  }
  return new Error('네트워크 연결을 확인해주세요.')
}

// AbortController helper
export function createAbortController(): AbortController {
  return new AbortController()
}

// Articles & Tracking
export async function trackArticle(input: TrackInput, signal?: AbortSignal): Promise<TrackResponse> {
  const { data } = await api.post<TrackResponse>('/articles/track', input, { signal })
  return data
}

export async function confirmTracking(input: ConfirmInput): Promise<ConfirmResponse> {
  const { data } = await api.post<ConfirmResponse>('/articles/confirm', input)
  return data
}

export async function getArticle(articleId: string): Promise<Article> {
  const { data } = await api.get<Article>(`/articles/${articleId}`)
  return data
}

// Timeline
export async function getTrackingStatus(trackingId: string, signal?: AbortSignal): Promise<TrackingStatus> {
  const { data } = await api.get<TrackingStatus>(`/timeline/${trackingId}/status`, { signal })
  return data
}

export async function getTimeline(trackingId: string): Promise<TimelineResponse> {
  const { data } = await api.get<TimelineResponse>(`/timeline/${trackingId}`)
  return data
}

// Search
export async function searchNews(
  query: string,
  limit: number = 10,
): Promise<TrackCandidate[]> {
  const { data } = await api.get<TrackCandidate[]>('/search/news', {
    params: { q: query, limit },
  })
  return data
}

// Trends
export async function getHotTrends(
  period: '24h' | '7d' | '30d' = '24h',
): Promise<TrendItem[]> {
  const { data } = await api.get<TrendItem[]>('/trends/hot', {
    params: { period },
  })
  return data
}

export async function getPopularSearches(): Promise<PopularSearch[]> {
  const { data } = await api.get<PopularSearch[]>('/trends/popular-searches')
  return data
}

export async function getStats(): Promise<StatsOverview> {
  const { data } = await api.get<StatsOverview>('/trends/stats')
  return data
}

// Article-based Trends
export async function getArticleTrends(
  period: '24h' | '7d' | '30d' = '24h',
): Promise<ArticleTrendsResponse> {
  const { data } = await api.get<ArticleTrendsResponse>('/trends/article-trends', {
    params: { period },
  })
  return data
}

export async function getRecentArticles(
  limit: number = 30,
  category?: string,
): Promise<RecentArticleItem[]> {
  const { data } = await api.get<RecentArticleItem[]>('/trends/recent-articles', {
    params: { limit, ...(category ? { category } : {}) },
  })
  return data
}

// Crawl Status
export async function getCrawlStatus(): Promise<CrawlStatus> {
  const { data } = await api.get<CrawlStatus>('/trends/crawl-status')
  return data
}
