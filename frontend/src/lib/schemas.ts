import { z } from 'zod'

// Article Trends
export const ClusterArticleSchema = z.object({
  id: z.string(),
  title: z.string(),
  publisher: z.string().nullable(),
  published_at: z.string().nullable(),
  created_at: z.string(),
  url: z.string(),
  category: z.string().nullable(),
  similarity_score: z.number(),
  cluster_reason: z.string().nullable().optional(),
})

export const TopicClusterSchema = z.object({
  cluster_id: z.string(),
  title: z.string(),
  article_count: z.number(),
  publishers: z.array(z.string()),
  categories: z.array(z.string()),
  first_seen: z.string(),
  last_seen: z.string(),
  avg_similarity: z.number(),
  representative_article: ClusterArticleSchema,
  articles: z.array(ClusterArticleSchema),
  growth_rate: z.number(),
})

export const ArticleTrendsResponseSchema = z.object({
  clusters: z.array(TopicClusterSchema),
  total_articles: z.number(),
  total_clusters: z.number(),
  period: z.string(),
  generated_at: z.string(),
  category_distribution: z.record(z.string(), z.number()),
  publisher_distribution: z.record(z.string(), z.number()),
  hourly_counts: z.array(z.object({ hour: z.string(), count: z.number() })),
})

export const StatsOverviewSchema = z.object({
  total_trackings: z.number(),
  total_articles: z.number(),
  active_trackings: z.number(),
  embedded_articles: z.number(),
  recent_articles_24h: z.number(),
  last_crawl_at: z.string().nullable(),
  category_counts: z.record(z.string(), z.number()),
})

export const TrackingStatusSchema = z.object({
  tracking_id: z.string(),
  status: z.enum(['pending', 'processing', 'completed', 'failed', 'error']),
  progress: z.number(),
  total_articles: z.number(),
  tracking_type: z.enum(['instant', 'live']),
  message: z.string(),
})

export const CrawlStatusSchema = z.object({
  phase: z.enum(['idle', 'fetching', 'crawling', 'embedding']),
  started_at: z.string().nullable(),
  detail: z.string().nullable(),
})

// Track & Search
export const TrackCandidateSchema = z.object({
  title: z.string(),
  url: z.string(),
  publisher: z.string().nullable(),
  published_at: z.string().nullable(),
})

export const ArticleSchema = z.object({
  id: z.string(),
  url: z.string(),
  title: z.string(),
  content: z.string().nullable(),
  summary: z.string().nullable(),
  author: z.string().nullable(),
  publisher: z.string().nullable(),
  publisher_domain: z.string().nullable(),
  published_at: z.string().nullable(),
  language: z.string().nullable(),
  created_at: z.string(),
})

export const TrackResponseSchema = z.object({
  input_type: z.enum(['url', 'title']),
  article: ArticleSchema.nullable(),
  candidates: z.array(TrackCandidateSchema),
})

export const ConfirmResponseSchema = z.object({
  tracking_id: z.string(),
  status: z.string(),
  tracking_type: z.enum(['instant', 'live']),
  message: z.string(),
})

export const RecentArticleItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  publisher: z.string().nullable(),
  published_at: z.string().nullable(),
  created_at: z.string(),
  url: z.string(),
  category: z.string().nullable(),
})

// Trend Comparison
export const TrendComparisonSchema = z.object({
  period_a: z.string(),
  period_b: z.string(),
  summary: z.object({
    total_a: z.number(),
    total_b: z.number(),
    clusters_a: z.number(),
    clusters_b: z.number(),
  }),
  category_changes: z.record(z.string(), z.object({
    period_a: z.number(),
    period_b: z.number(),
    change: z.number(),
    change_pct: z.number(),
  })),
  new_topics: z.array(z.object({
    title: z.string(),
    article_count: z.number(),
    categories: z.array(z.string()),
  })),
  growing_topics: z.array(z.object({
    title: z.string(),
    article_count: z.number(),
    growth_rate: z.number(),
  })),
})

export function safeParse<T>(schema: z.ZodSchema<T>, data: unknown): T {
  const result = schema.safeParse(data)
  if (result.success) return result.data
  console.warn('API response validation warning:', result.error)
  return data as T  // Fall through on validation failure (log only)
}
