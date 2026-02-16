import { describe, it, expect, vi } from 'vitest'
import {
  safeParse,
  ClusterArticleSchema,
  ArticleTrendsResponseSchema,
  StatsOverviewSchema,
  TrackingStatusSchema,
  CrawlStatusSchema,
  TrackResponseSchema,
  ConfirmResponseSchema,
  TrendComparisonSchema,
} from './schemas'

describe('Zod schemas', () => {
  describe('safeParse', () => {
    it('returns parsed data for valid input', () => {
      const data = { phase: 'idle', started_at: null, detail: null }
      const result = safeParse(CrawlStatusSchema, data)
      expect(result).toEqual(data)
    })

    it('returns raw data and warns for invalid input', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const data = { phase: 'unknown_phase', started_at: null, detail: null }
      const result = safeParse(CrawlStatusSchema, data)
      expect(result).toEqual(data) // falls through
      expect(consoleSpy).toHaveBeenCalled()
      consoleSpy.mockRestore()
    })
  })

  describe('ClusterArticleSchema', () => {
    it('validates a valid cluster article', () => {
      const data = {
        id: '1',
        title: '기사 제목',
        publisher: '언론사',
        published_at: '2026-01-01T00:00:00Z',
        created_at: '2026-01-01T00:00:00Z',
        url: 'https://example.com',
        category: 'politics',
        similarity_score: 0.85,
      }
      const result = ClusterArticleSchema.safeParse(data)
      expect(result.success).toBe(true)
    })

    it('accepts nullable fields', () => {
      const data = {
        id: '1',
        title: '제목',
        publisher: null,
        published_at: null,
        created_at: '2026-01-01',
        url: 'https://example.com',
        category: null,
        similarity_score: 1.0,
      }
      const result = ClusterArticleSchema.safeParse(data)
      expect(result.success).toBe(true)
    })
  })

  describe('StatsOverviewSchema', () => {
    it('validates a valid stats response', () => {
      const data = {
        total_trackings: 10,
        total_articles: 50,
        active_trackings: 2,
        embedded_articles: 45,
        recent_articles_24h: 12,
        last_crawl_at: null,
        category_counts: { politics: 5, economy: 3 },
      }
      const result = StatsOverviewSchema.safeParse(data)
      expect(result.success).toBe(true)
    })
  })

  describe('TrackingStatusSchema', () => {
    it('validates all status types', () => {
      for (const status of ['pending', 'processing', 'completed', 'failed', 'error']) {
        const data = {
          tracking_id: 'abc',
          status,
          progress: 50,
          total_articles: 10,
          tracking_type: 'instant',
          message: '처리중',
        }
        const result = TrackingStatusSchema.safeParse(data)
        expect(result.success).toBe(true)
      }
    })

    it('rejects invalid status', () => {
      const data = {
        tracking_id: 'abc',
        status: 'invalid',
        progress: 50,
        total_articles: 10,
        tracking_type: 'instant',
        message: '',
      }
      const result = TrackingStatusSchema.safeParse(data)
      expect(result.success).toBe(false)
    })
  })

  describe('CrawlStatusSchema', () => {
    it('validates all phase types', () => {
      for (const phase of ['idle', 'fetching', 'crawling', 'embedding']) {
        const result = CrawlStatusSchema.safeParse({ phase, started_at: null, detail: null })
        expect(result.success).toBe(true)
      }
    })
  })

  describe('TrackResponseSchema', () => {
    it('validates track response with article', () => {
      const data = {
        input_type: 'url',
        article: {
          id: '1', url: 'https://example.com', title: '제목',
          content: '내용', summary: null, author: null,
          publisher: '언론사', publisher_domain: null,
          published_at: '2026-01-01', language: 'ko', created_at: '2026-01-01',
        },
        candidates: [],
      }
      const result = TrackResponseSchema.safeParse(data)
      expect(result.success).toBe(true)
    })

    it('validates track response with candidates', () => {
      const data = {
        input_type: 'title',
        article: null,
        candidates: [
          { title: '기사1', url: 'https://example.com/1', publisher: '언론사', published_at: '2026-01-01' },
          { title: '기사2', url: 'https://example.com/2', publisher: null, published_at: null },
        ],
      }
      const result = TrackResponseSchema.safeParse(data)
      expect(result.success).toBe(true)
    })
  })

  describe('TrendComparisonSchema', () => {
    it('validates a comparison response', () => {
      const data = {
        period_a: '24h',
        period_b: '7d',
        summary: { total_a: 100, total_b: 200, clusters_a: 5, clusters_b: 8 },
        category_changes: {
          politics: { period_a: 30, period_b: 20, change: 10, change_pct: 50 },
        },
        new_topics: [
          { title: '새 토픽', article_count: 3, categories: ['politics'] },
        ],
        growing_topics: [
          { title: '성장 토픽', article_count: 5, growth_rate: 2.5 },
        ],
      }
      const result = TrendComparisonSchema.safeParse(data)
      expect(result.success).toBe(true)
    })

    it('validates with empty arrays', () => {
      const data = {
        period_a: '24h',
        period_b: '7d',
        summary: { total_a: 0, total_b: 0, clusters_a: 0, clusters_b: 0 },
        category_changes: {},
        new_topics: [],
        growing_topics: [],
      }
      const result = TrendComparisonSchema.safeParse(data)
      expect(result.success).toBe(true)
    })
  })

  describe('ConfirmResponseSchema', () => {
    it('validates confirm response', () => {
      const data = {
        tracking_id: 'abc-123',
        status: 'processing',
        tracking_type: 'instant',
        message: '추적을 시작합니다',
      }
      const result = ConfirmResponseSchema.safeParse(data)
      expect(result.success).toBe(true)
    })
  })

  describe('ArticleTrendsResponseSchema', () => {
    it('validates a full trends response', () => {
      const data = {
        clusters: [],
        total_articles: 100,
        total_clusters: 5,
        period: '24h',
        generated_at: '2026-01-01T00:00:00Z',
        category_distribution: { politics: 20, economy: 15 },
        publisher_distribution: { '한겨레': 10, '조선일보': 8 },
        hourly_counts: [{ hour: '2026-01-01T10:00:00Z', count: 5 }],
      }
      const result = ArticleTrendsResponseSchema.safeParse(data)
      expect(result.success).toBe(true)
    })
  })
})
