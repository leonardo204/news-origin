import { useState, useEffect } from 'react'
import {
  Rss,
  GitMerge,
  Brain,
  FlaskConical,
  Monitor,
  RefreshCw,
  Lock,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { fetchSettings } from '@/services/adminApi'

interface SettingsData {
  crawling: {
    interval_minutes: number
    categories: string[]
    feed_limit_per_category: number
    publisher_feed_limit: number
    max_articles_per_run: number
    retention_days: number
  }
  clustering: {
    merge_threshold: number
    max_component: number
  }
  embedding: {
    model: string
    dimension: number
  }
  mlops: {
    min_quality: number
    min_samples: number
    eval_sample_size: number
    reextract_days: number
    max_versions: number
  }
  system: {
    app_env: string
    debug: boolean
  }
}

const CATEGORY_LABELS: Record<string, string> = {
  headlines: '헤드라인',
  politics: '정치',
  economy: '경제',
  society: '사회',
  tech: '기술',
  entertainment: '연예',
  world: '세계',
  sports: '스포츠',
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="h-40 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800"
        />
      ))}
    </div>
  )
}

function ConfigItem({
  label,
  value,
}: {
  label: string
  value: string | number | boolean
}) {
  let displayValue: React.ReactNode
  if (typeof value === 'boolean') {
    displayValue = (
      <span
        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
          value
            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
            : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
        }`}
      >
        {value ? '활성' : '비활성'}
      </span>
    )
  } else {
    displayValue = (
      <span className="font-medium text-gray-900 dark:text-gray-100">
        {String(value)}
      </span>
    )
  }

  return (
    <div className="flex items-center justify-between py-2.5 border-b border-gray-100 last:border-0 dark:border-gray-800">
      <span className="text-sm text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-sm">{displayValue}</span>
    </div>
  )
}

export default function SettingsPage() {
  const [data, setData] = useState<SettingsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const { data: res } = await fetchSettings()
      setData(res)
      setError(null)
    } catch (err) {
      console.error('Settings fetch error:', err)
      setError('설정 데이터를 불러오는데 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          설정
        </h2>
        <LoadingSkeleton />
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          설정
        </h2>
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-gray-500 dark:text-gray-400">{error}</p>
            <button
              onClick={loadData}
              className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
            >
              <RefreshCw className="h-4 w-4" />
              다시 시도
            </button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          설정 (읽기 전용)
        </h2>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-500 dark:bg-gray-800 dark:text-gray-400">
            <Lock className="h-3 w-3" />
            읽기 전용
          </span>
          <button
            onClick={loadData}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            새로고침
          </button>
        </div>
      </div>

      {/* Crawling Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Rss className="h-5 w-5 text-orange-500" />
            크롤링 설정
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ConfigItem
            label="수집 주기"
            value={`${data.crawling.interval_minutes}분`}
          />
          <div className="flex items-center justify-between py-2.5 border-b border-gray-100 dark:border-gray-800">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              카테고리
            </span>
            <div className="flex flex-wrap gap-1">
              {data.crawling.categories.map((cat) => (
                <span
                  key={cat}
                  className="inline-flex rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                >
                  {CATEGORY_LABELS[cat] || cat}
                </span>
              ))}
            </div>
          </div>
          <ConfigItem
            label="카테고리당 피드 제한"
            value={`${data.crawling.feed_limit_per_category}건`}
          />
          <ConfigItem
            label="언론사별 피드 제한"
            value={`${data.crawling.publisher_feed_limit}건`}
          />
          <ConfigItem
            label="실행당 최대 기사 수"
            value={`${data.crawling.max_articles_per_run}건`}
          />
          <ConfigItem
            label="보존 기간"
            value={`${data.crawling.retention_days}일`}
          />
        </CardContent>
      </Card>

      {/* Clustering Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitMerge className="h-5 w-5 text-purple-500" />
            클러스터링 설정
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ConfigItem
            label="병합 임계값 (cosine similarity)"
            value={data.clustering.merge_threshold}
          />
          <ConfigItem
            label="최대 컴포넌트 기사 수"
            value={`${data.clustering.max_component}건`}
          />
        </CardContent>
      </Card>

      {/* Embedding Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-blue-500" />
            임베딩 설정
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ConfigItem label="모델" value={data.embedding.model} />
          <ConfigItem
            label="차원 (dimension)"
            value={data.embedding.dimension}
          />
        </CardContent>
      </Card>

      {/* MLOps Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5 text-emerald-500" />
            MLOps 설정
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ConfigItem
            label="최소 품질 기준"
            value={data.mlops.min_quality}
          />
          <ConfigItem
            label="최소 학습 샘플 수"
            value={`${data.mlops.min_samples}건`}
          />
          <ConfigItem
            label="평가 샘플 크기"
            value={`${data.mlops.eval_sample_size}건`}
          />
          <ConfigItem
            label="재추출 기간"
            value={`${data.mlops.reextract_days}일`}
          />
          <ConfigItem
            label="최대 모델 버전 수"
            value={`${data.mlops.max_versions}개`}
          />
        </CardContent>
      </Card>

      {/* System Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Monitor className="h-5 w-5 text-gray-500" />
            시스템
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ConfigItem label="환경" value={data.system.app_env} />
          <ConfigItem label="디버그 모드" value={data.system.debug} />
        </CardContent>
      </Card>
    </div>
  )
}
