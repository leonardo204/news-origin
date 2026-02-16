import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { getErrorMessage, isRetryableError, type ApiError } from '@/lib/errors'
import { safeParse,
  ArticleTrendsResponseSchema,
  StatsOverviewSchema,
  TrackingStatusSchema,
  CrawlStatusSchema,
  TrackResponseSchema,
  ConfirmResponseSchema,
  RecentArticleItemSchema,
  TrendComparisonSchema,
} from '@/lib/schemas'
import type {
  TrackInput,
  TrackResponse,
  ConfirmInput,
  ConfirmResponse,
  LiveTrackInput,
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
  TrendComparison,
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Retry config
const MAX_RETRIES = 2
const INITIAL_RETRY_DELAY = 1000

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

interface RetryableAxiosConfig extends InternalAxiosRequestConfig {
  __retryCount?: number
}

// Response interceptor with retry for transient failures
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config
    if (!config) return Promise.reject(formatError(error))

    const retryableConfig = config as RetryableAxiosConfig
    const retryCount: number = retryableConfig.__retryCount || 0

    // API 에러 객체 생성
    const apiError: ApiError = {
      name: 'ApiError',
      message: error.message,
      code: error.code,
      status: error.response?.status,
    }

    // 4xx 에러는 재시도하지 않음 (POST는 기본적으로 재시도 안 함)
    const shouldRetry =
      config.method?.toUpperCase() !== 'POST' &&
      isRetryableError(apiError) &&
      retryCount < MAX_RETRIES

    if (shouldRetry) {
      retryableConfig.__retryCount = retryCount + 1
      // Exponential backoff: 1초, 3초
      const delay = INITIAL_RETRY_DELAY * Math.pow(3, retryCount)
      await sleep(delay)
      return api(config)
    }

    return Promise.reject(formatError(error))
  },
)

function formatError(error: AxiosError): ApiError {
  const apiError: ApiError = {
    name: 'ApiError',
    message: error.message,
    code: error.code,
    status: error.response?.status,
  }

  // 서버에서 반환한 상세 메시지 우선 사용
  if (error.response) {
    const detail = (error.response.data as Record<string, unknown>)?.detail
    if (typeof detail === 'string') {
      apiError.message = detail
      return apiError
    }
  }

  // 에러 유틸리티로 메시지 변환
  apiError.message = getErrorMessage(apiError)
  return apiError
}

// AbortController helper
export function createAbortController(): AbortController {
  return new AbortController()
}

// Articles & Tracking
export async function trackArticle(input: TrackInput, signal?: AbortSignal): Promise<TrackResponse> {
  const { data } = await api.post('/articles/track', input, { signal })
  return safeParse(TrackResponseSchema, data) as TrackResponse
}

export async function confirmTracking(input: ConfirmInput): Promise<ConfirmResponse> {
  const { data } = await api.post('/articles/confirm', input)
  return safeParse(ConfirmResponseSchema, data) as ConfirmResponse
}

export async function liveTrack(input: LiveTrackInput): Promise<ConfirmResponse> {
  const { data } = await api.post('/articles/live-track', input)
  return safeParse(ConfirmResponseSchema, data) as ConfirmResponse
}

export async function getArticle(articleId: string): Promise<Article> {
  const { data } = await api.get<Article>(`/articles/${articleId}`)
  return data
}

// Timeline
export async function getTrackingStatus(trackingId: string, signal?: AbortSignal): Promise<TrackingStatus> {
  const { data } = await api.get(`/timeline/${trackingId}/status`, { signal })
  return safeParse(TrackingStatusSchema, data) as TrackingStatus
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
  const { data } = await api.get('/trends/stats')
  return safeParse(StatsOverviewSchema, data) as StatsOverview
}

// Article-based Trends
export async function getArticleTrends(
  period: '24h' | '7d' | '30d' = '24h',
): Promise<ArticleTrendsResponse> {
  const { data } = await api.get('/trends/article-trends', {
    params: { period },
  })
  return safeParse(ArticleTrendsResponseSchema, data) as ArticleTrendsResponse
}

export async function getRecentArticles(
  limit: number = 30,
  category?: string,
): Promise<RecentArticleItem[]> {
  const { data } = await api.get('/trends/recent-articles', {
    params: { limit, ...(category ? { category } : {}) },
  })
  return (data as unknown[]).map((item) => safeParse(RecentArticleItemSchema, item)) as RecentArticleItem[]
}

// Crawl Status
export async function getCrawlStatus(): Promise<CrawlStatus> {
  const { data } = await api.get('/trends/crawl-status')
  return safeParse(CrawlStatusSchema, data) as CrawlStatus
}

// Trend Comparison
export async function compareTrends(
  periodA: '24h' | '7d' | '30d' = '24h',
  periodB: '24h' | '7d' | '30d' = '7d',
): Promise<TrendComparison> {
  const { data } = await api.get('/trends/compare', {
    params: { period_a: periodA, period_b: periodB },
  })
  return safeParse(TrendComparisonSchema, data) as TrendComparison
}
