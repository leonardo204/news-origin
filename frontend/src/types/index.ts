// Article types
export interface Article {
  id: string
  url: string
  title: string
  content: string | null
  summary: string | null
  author: string | null
  publisher: string | null
  publisher_domain: string | null
  published_at: string | null
  language: string | null
  created_at: string
}

// Similarity categories
export type SimilarityCategory = 'same' | 'derivative' | 'related'

// Lifecycle stages
export type LifecycleStage =
  | 'origin'
  | 'spread'
  | 'explosion'
  | 'sustained'
  | 'fadeout'
  | 'resurge'

// Track request/response
export interface TrackInput {
  text: string
  title?: string
  publisher?: string
  published_at?: string
}

export interface TrackCandidate {
  title: string
  url: string
  publisher: string | null
  published_at: string | null
}

export interface TrackResponse {
  input_type: 'url' | 'title'
  article: Article | null
  candidates: TrackCandidate[]
}

export interface ConfirmInput {
  article_id: string
  tracking_type?: 'instant' | 'live'
}

export interface LiveTrackInput {
  tracking_id: string
}

export interface ConfirmResponse {
  tracking_id: string
  status: string
  tracking_type: 'instant' | 'live'
  message: string
}

// Tracking status
export interface TrackingStatus {
  tracking_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'error'
  progress: number
  total_articles: number
  tracking_type: 'instant' | 'live'
  message: string
}

// Graph visualization (AntV G6)
export interface GraphNode {
  id: string
  title: string
  publisher: string
  published_at: string | null
  similarity_score: number
  similarity_category: SimilarityCategory
  lifecycle_stage: LifecycleStage
  is_origin: boolean
  is_user_selected: boolean
  url: string
}

export interface GraphEdge {
  source: string
  target: string
  similarity_score: number
  similarity_category: SimilarityCategory
}

// Timeline (ECharts)
export interface TimelineItem {
  article_id: string
  title: string
  publisher: string
  published_at: string
  similarity_score: number
  lifecycle_stage: LifecycleStage
  url: string | null
  is_origin: boolean
  is_user_selected: boolean
}

export interface DensityPoint {
  time: string
  count: number
}

export interface ExplosionPoint {
  start_time: string
  end_time: string
  peak_count: number
  article_count: number
}

export interface LifecycleSummary {
  origin_time: string | null
  fadeout_time: string | null
  peak_hour: string | null
  total_duration_hours: number | null
  total_articles: number
  stage_counts: Record<LifecycleStage, number>
}

// Full timeline response
export interface TimelineResponse {
  tracking_id: string
  tracking_type: 'instant' | 'live'
  origin_article: Article
  input_article_id: string | null
  graph: {
    nodes: GraphNode[]
    edges: GraphEdge[]
  }
  timeline: TimelineItem[]
  density: DensityPoint[]
  explosions: ExplosionPoint[]
  lifecycle: LifecycleSummary
}

// Trends
export interface TrendItem {
  title: string
  tracking_count: number
  latest_tracking_id: string
  last_tracked_at: string
}

export interface PopularSearch {
  query: string
  count: number
}

export interface StatsOverview {
  total_trackings: number
  total_articles: number
  active_trackings: number
  embedded_articles: number
  recent_articles_24h: number
  last_crawl_at: string | null
  category_counts: Record<string, number>
}

// View mode for visualization
export type ViewMode = 'graph' | 'timeline' | 'density'

// Article-based Trends
export interface ClusterArticle {
  id: string
  title: string
  publisher: string | null
  published_at: string | null
  created_at: string
  url: string
  category: string | null
  similarity_score: number
  cluster_reason: string | null
}

export interface TopicCluster {
  cluster_id: string
  title: string
  article_count: number
  publishers: string[]
  categories: string[]
  first_seen: string
  last_seen: string
  avg_similarity: number
  representative_article: ClusterArticle
  articles: ClusterArticle[]
  growth_rate: number
}

export interface ArticleTrendsResponse {
  clusters: TopicCluster[]
  total_articles: number
  total_clusters: number
  period: string
  generated_at: string
  category_distribution: Record<string, number>
  publisher_distribution: Record<string, number>
  hourly_counts: Array<{ hour: string; count: number }>
}

export interface RecentArticleItem {
  id: string
  title: string
  publisher: string | null
  published_at: string | null
  created_at: string
  url: string
  category: string | null
}

// Crawl pipeline status
export interface CrawlStatus {
  phase: 'idle' | 'fetching' | 'crawling' | 'embedding'
  started_at: string | null
  detail: string | null
}

// Trend Comparison
export interface TrendComparison {
  period_a: string
  period_b: string
  summary: {
    total_a: number
    total_b: number
    clusters_a: number
    clusters_b: number
  }
  category_changes: Record<
    string,
    {
      period_a: number
      period_b: number
      change: number
      change_pct: number
    }
  >
  new_topics: Array<{
    title: string
    article_count: number
    categories: string[]
  }>
  growing_topics: Array<{
    title: string
    article_count: number
    growth_rate: number
  }>
}
