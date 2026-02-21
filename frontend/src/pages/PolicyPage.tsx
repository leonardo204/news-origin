import { Link } from 'react-router-dom'
import { ArrowLeft, Shield } from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'

export default function PolicyPage() {
  usePageTitle('운영 정책')

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:py-12">
      <Link
        to="/"
        className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        홈으로
      </Link>

      <div className="mb-8 flex items-center gap-3">
        <Shield className="h-7 w-7 text-lifecycle-origin" />
        <h1 className="text-2xl font-bold">운영 정책</h1>
      </div>

      <div className="prose prose-sm dark:prose-invert max-w-none space-y-6 text-foreground">
        <section>
          <h2 className="text-lg font-semibold">서비스 목적</h2>
          <p className="leading-relaxed text-muted-foreground">
            News Origin은 개인 비상업적 뉴스 분석 학습 프로젝트입니다.
            뉴스 기사의 전파 경로와 트렌드를 시각적으로 분석하는 것을 목적으로 합니다.
          </p>
        </section>

        <hr className="border-border" />

        <section>
          <h2 className="text-lg font-semibold">뉴스 콘텐츠 이용</h2>
          <p className="leading-relaxed text-muted-foreground">
            본 서비스는 각 언론사가 공개한 RSS 피드를 기반으로 동작합니다.
            기사의 <strong className="text-foreground">제목, 언론사명, 발행일 등 메타데이터</strong>만
            저장하며, 기사 본문은 저장하지 않습니다.
          </p>
        </section>

        <hr className="border-border" />

        <section>
          <h2 className="text-lg font-semibold">원문 링크 제공</h2>
          <p className="leading-relaxed text-muted-foreground">
            모든 기사는 원본 언론사 웹사이트로의 링크를 제공하며,
            사용자가 기사 내용을 확인하려면 원본 사이트를 방문해야 합니다.
          </p>
        </section>

        <hr className="border-border" />

        <section>
          <h2 className="text-lg font-semibold">저작권 존중</h2>
          <p className="leading-relaxed text-muted-foreground">
            저작권자 또는 언론사의 요청이 있을 경우 해당 콘텐츠를 즉시 삭제합니다.
            삭제 요청은 아래 연락처로 보내주시기 바랍니다.
          </p>
        </section>

        <hr className="border-border" />

        <section>
          <h2 className="text-lg font-semibold">AI/NER 학습 정책</h2>
          <p className="leading-relaxed text-muted-foreground">
            본 서비스는 뉴스 제목에서 인명, 기관명 등 핵심 키워드를 추출하기 위해
            NER(Named Entity Recognition) 모델을 운용합니다.
            AI 학습 금지를 명시한 언론사(한겨레 등)의 기사는 NER 학습 데이터에서
            제외됩니다.
          </p>
        </section>

        <hr className="border-border" />

        <section>
          <h2 className="text-lg font-semibold">수익 활동 없음</h2>
          <p className="leading-relaxed text-muted-foreground">
            본 서비스는 광고, 유료 구독, 상업적 API 제공 등 일체의 수익 활동을
            하지 않습니다. 순수한 개인 학습 및 연구 목적으로만 운영됩니다.
          </p>
        </section>

        <hr className="border-border" />

        <section>
          <h2 className="text-lg font-semibold">연락처</h2>
          <p className="leading-relaxed text-muted-foreground">
            운영 관련 문의 및 콘텐츠 삭제 요청은 관리자 이메일로 연락해 주세요.
          </p>
          <p className="mt-2">
            <a
              href="mailto:zerolive7@gmail.com"
              className="text-lifecycle-origin hover:underline"
            >
              zerolive7@gmail.com
            </a>
          </p>
        </section>
      </div>
    </div>
  )
}
