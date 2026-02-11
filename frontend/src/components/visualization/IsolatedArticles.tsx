import { AlertCircle, ExternalLink, Building2, Clock } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { formatDate } from '@/lib/utils'
import type { Article } from '@/types'

interface IsolatedArticlesProps {
  articles: Article[]
}

export default function IsolatedArticles({ articles }: IsolatedArticlesProps) {
  if (articles.length === 0) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-lifecycle-isolated" />
          고립 기사
          <Badge stage="isolated">{articles.length}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-xs text-muted-foreground">
          다른 기사와의 유사도가 낮아 독립적으로 작성된 것으로 보이는 기사들입니다.
        </p>
        <div className="space-y-2">
          {articles.map((article) => (
            <div
              key={article.id}
              className="flex items-start justify-between gap-2 rounded-md bg-secondary/30 p-2"
            >
              <div className="flex-1 space-y-1">
                <p className="text-sm font-medium leading-tight">{article.title}</p>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  {article.publisher && (
                    <span className="flex items-center gap-1">
                      <Building2 className="h-3 w-3" />
                      {article.publisher}
                    </span>
                  )}
                  {article.published_at && (
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatDate(article.published_at)}
                    </span>
                  )}
                </div>
              </div>
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-lifecycle-origin"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
