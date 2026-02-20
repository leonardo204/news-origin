# News Origin - 서비스 고도화 TODO 리스트

> **작성일**: 2026-02-16
> **현재 버전**: v1.0.0 (Production)
> **분석 기준**: 백엔드/프론트엔드/인프라 전체 코드베이스 정밀 분석

---

## 목차

1. [우선순위 범례](#우선순위-범례)
2. [Backend 고도화](#1-backend-고도화)
3. [Frontend 고도화](#2-frontend-고도화)
4. [Infrastructure & DevOps](#3-infrastructure--devops)
5. [Product & 신규 기능](#4-product--신규-기능)
6. [코드 품질 & 리팩토링](#5-코드-품질--리팩토링)

---

## 우선순위 범례

| 등급 | 의미 | 기준 |
|------|------|------|
| **P0** | 즉시 | 성능/안정성/보안에 직접적 영향 |
| **P1** | 높음 | 운영 효율성 및 사용자 경험 개선 |
| **P2** | 중간 | 코드 품질/유지보수성 향상 |
| **P3** | 낮음 | 향후 확장성/편의성 |

---

## 참고: 현재 임베딩 아키텍처

> ~~CLAUDE.md에는 `paraphrase-multilingual-mpnet-base-v2 (768차원)` 로컬 모델로 기재되어 있으나,~~
> ~~v0.2.0 마이그레이션으로 **Azure OpenAI text-embedding-3-large (1024차원)** API 방식으로 전환 완료.~~
> ~~로컬 모델 제거로 Celery Worker 메모리 ~1GB 절감됨. CLAUDE.md 업데이트 필요.~~
> **해결됨**: CLAUDE.md 업데이트 완료 (2026-02-16)

---

## 1. Backend 고도화

### P0 - 즉시

- [x] **캐시 무효화 하드코딩 제거** ✅
  - 파일: `backend/app/workers/tasks.py` (39회 `cache_delete` 호출)
  - 현재: 동일한 캐시 키 목록이 3곳 이상 반복 (fetch_trending, analyze_instant, analyze_live)
  - 개선: `invalidate_all_trend_caches()` 헬퍼 함수로 통합

- [x] **Celery 태스크 동시실행 방지 (race condition)** ✅
  - 파일: `backend/app/workers/tasks.py:48-82`
  - 현재: `fetch_trending_news`가 30분 간격이지만, 이전 실행이 끝나기 전 다음 실행 시작 가능
  - 개선: Redis distributed lock 또는 `celery-singleton` 패턴 적용

### P1 - 높음

- [ ] **API 페이지네이션 추가**
  - 파일: `backend/app/api/routes/trends.py`, `timeline.py`
  - 현재: 타임라인/트렌드 기사 목록이 전체 반환 (대량 데이터 시 응답 지연)
  - 개선: cursor 기반 페이지네이션 + 프론트엔드 무한스크롤

- [x] **search_logs 테이블 관리** ✅
  - 현재: 검색 로그가 무한 증가, 정리 정책 없음
  - 개선: `cleanup_old_articles`에 search_logs 정리 로직 추가 (90일 기준)

- [x] **Qdrant 벡터 검색 배치화** ✅
  - 파일: `backend/app/core/trend_clustering.py:280-284`
  - 현재: 기사마다 개별 `search_similar()` 호출 (N+1 패턴)
  - 개선: Qdrant batch search API 활용하여 한 번에 검색

- [x] **RSS 피드 수집 병렬화** ✅
  - 파일: `backend/app/services/news_feed.py`
  - 현재: 카테고리별 순차 `await` 루프 (이미 httpx async 사용)
  - 개선: `asyncio.gather()`로 카테고리 피드 동시 요청 (이미 async 인프라 갖춤)

### P2 - 중간

- [x] **코사인 유사도 계산 최적화** ✅
  - 파일: `backend/app/core/trend_clustering.py:47-54`
  - 현재: 순수 Python `sum(a*b for a,b in zip(...))` 루프 → 1024차원 벡터에서 느림
  - 개선: `numpy` dot/norm 사용 시 10-50x 성능 향상
  - 트레이드오프: numpy 추가 시 Docker 이미지 ~50MB, 런타임 ~20MB 증가
  - 참고: 클러스터링에서 최대 500기사 × 100 유사도 = 50,000회 호출 가능
  - 대안: 프로파일링으로 실제 병목 확인 후 결정

- [x] **Article JSONB 인덱스 추가** ✅
  - 파일: `backend/app/models/article.py`
  - 현재: `metadata_->>'category'` 필터링에 인덱스 없음
  - 개선: GIN 인덱스 또는 `category` 컬럼 분리

- [x] **에러 응답 표준화** ✅
  - 현재: 일부 API에서 raw exception 메시지 반환
  - 개선: RFC 7807 Problem Details 형식 통일

- [x] **Azure OpenAI API 재시도/fallback** ✅
  - 파일: `backend/app/services/azure_openai.py`
  - 현재: 단일 API 엔드포인트, 실패 시 전체 배치 실패
  - 개선: exponential backoff + 대체 엔드포인트 설정

### P3 - 낮음

- [ ] **1회성 마이그레이션 태스크 정리**
  - 파일: `backend/app/workers/tasks.py:919-1095`
  - 현재: `migrate_article_categories`, `reembed_all_articles`가 여전히 등록됨
  - 개선: 완료 확인 후 코드 제거 또는 별도 스크립트로 분리

- [ ] **`get_article_text()` 미사용 파라미터 정리**
  - 파일: `backend/app/services/embedding.py:34-43`
  - 현재: `content` 파라미터가 하위 호환성으로만 존재 (실제 미사용)
  - 개선: 호출부 일괄 수정 후 파라미터 제거

---

## 2. Frontend 고도화

### P0 - 즉시

- [x] **번들 사이즈 최적화** ✅
  - 현재: ECharts + @antv/g6 = 약 2MB+ (초기 로드 시간 영향)
  - 개선:
    - ECharts tree-shaking (`echarts/core`에서 필요한 차트만 import)
    - G6 lazy load 확인 (이미 적용됨, 번들 분석 필요)
    - `vite-plugin-visualizer`로 번들 분석 대시보드 추가

- [x] **에러 바운더리 강화 & API 에러 처리 고도화** ✅
  - 현재: ErrorBoundary 컴포넌트 존재 (`frontend/src/components/ui/ErrorBoundary.tsx`), App.tsx 루트에 적용됨
  - 개선:
    - API 에러별 한국어 메시지 매핑 (네트워크 끊김, 서버 500, 타임아웃, 429 등)
    - 페이지별 세분화된 ErrorBoundary (차트 실패 시 차트만 fallback)
    - API 호출 실패 시 자동 재시도 (exponential backoff)

### P1 - 높음

- [x] **전파 트리 그래프 대량 노드 처리** ✅
  - 파일: `frontend/src/components/visualization/PropagationGraph.tsx`
  - 현재: 노드 수 제한 없음 → 100+ 노드에서 렌더링 성능 저하
  - 개선: 노드 수 50개 초과 시 클러스터링/축소 표시, 확대 시 디테일 로드

- [x] **접근성(a11y) 개선** ✅
  - 현재: 기본 ARIA 라벨 일부 적용됨
  - 개선:
    - 차트 컴포넌트에 `aria-label`, `role="img"` 추가
    - 키보드 내비게이션 (Tab, Enter, Escape) 일관성 확인
    - 색상 대비 비율 검증 (lifecycle 색상 계열)

- [x] **모바일 UX 개선** ✅
  - 현재: 반응형 기본 적용, 모바일 인터랙션 미최적화
  - 개선:
    - 트렌드 카드 스와이프 지원
    - 타임라인 차트 터치 줌/패닝
    - 전파 트리 모바일 레이아웃 (가로 스크롤 → 세로 트리)

- [x] **트렌드 필터 아키텍처** ✅
  - 파일: `frontend/src/pages/TrendsPage.tsx`
  - 현재: 기간 필터만 존재 (24h, 7d, 30d)
  - 개선:
    - 카테고리 필터 (다중 선택)
    - 언론사 필터
    - 키워드 검색 필터
    - URL query param 연동 (공유 가능한 필터 상태)

### P2 - 중간

- [x] **토스트/알림 시스템** ✅
  - 현재: 공유 복사 시 인라인 상태 표시만 존재
  - 개선: 전역 토스트 큐 (성공/에러/경고), 자동 해제, 스택 표시

- [x] **빈 상태 UX 개선** ✅
  - 현재: 데이터 없을 때 "타임라인 데이터를 찾을 수 없습니다" 텍스트만 표시
  - 개선: 일러스트/아이콘 + 다음 행동 안내 (검색 제안, 인기 기사 추천)

- [x] **SSE 재연결 UX 표시** ✅
  - 파일: `frontend/src/components/layout/Header.tsx:30-83`
  - 현재: SSE 끊김 시 자동 재연결되지만 사용자에게 상태 표시 없음
  - 개선: 연결 상태 인디케이터 (연결됨/재연결 중/오프라인)

- [x] **다크/라이트 테마 토글** ✅
  - 현재: 다크 모드 고정
  - 개선: `prefers-color-scheme` 감지 + 수동 토글 (Tailwind dark: class 전환)

### P3 - 낮음

- [ ] **PWA 지원**
  - 현재: 일반 웹앱
  - 개선: manifest.json + service worker → 홈 화면 추가, 오프라인 기본 페이지

- [ ] **i18n 기반 다국어 지원**
  - 현재: 한국어 하드코딩
  - 개선: `react-i18next` 도입, 영어 지원

---

## 3. Infrastructure & DevOps

### P0 - 즉시

- [x] **DB 자동 백업** ✅
  - 현재: 백업 없음 → 데이터 유실 위험
  - 개선:
    - `pg_dump` cron job (매일 03:00, 7일 보존)
    - Qdrant snapshot 자동화
    - 백업 파일 외부 저장소 동기화 (선택)

- [ ] **HTTPS/SSL 적용**
  - 현재: HTTP only (포트 10880)
  - 전제: 도메인 확보 + DNS A 레코드 설정 필요
  - 개선:
    - Let's Encrypt certbot (standalone 또는 webroot 방식)
    - Nginx SSL 설정 (`ssl_certificate`, `ssl_protocols TLSv1.2 TLSv1.3`)
    - HTTP→HTTPS 301 리다이렉트
    - certbot auto-renewal cron (매월 갱신)
    - 도메인 미확보 시: 자체 서명 인증서로 전환 가능

- [x] **Celery 태스크 모니터링** ✅
  - 현재: 로그 기반 모니터링만 존재
  - 개선:
    - Flower 대시보드 (경량, Redis 백엔드 활용)
    - 태스크 실패 알림 (이메일/웹훅)
    - 태스크 실행 시간 메트릭

### P1 - 높음

- [x] **구조화된 로깅 (structured logging)** ✅
  - 현재: `logging.warning()` 문자열 기반 로그
  - 개선:
    - JSON 형식 로그 (python-json-logger)
    - 요청 ID 트레이싱 (correlation_id)
    - 로그 레벨 표준화 (INFO: 정상, WARNING: 주의, ERROR: 실패)

- [x] **CI/CD 파이프라인** ✅
  - 현재: 수동 배포 (`docker compose up -d --build`)
  - 개선:
    - GitHub Actions: lint → test → build → deploy
    - 스테이징 환경 분리
    - 롤백 전략 (이전 이미지 태깅)

- [x] **Graceful degradation** ✅
  - 현재: Qdrant/Redis 장애 시 전체 서비스 중단
  - 개선:
    - Qdrant 장애 시: 벡터 검색 비활성화, DB 기반 fallback
    - Redis 장애 시: 캐시 우회, SSE 비활성화
    - 헬스체크 엔드포인트에 의존 서비스 상태 포함

- [x] **Rate limiting 적용** ✅
  - 현재: API 호출 제한 없음
  - 개선:
    - Nginx `limit_req_zone` (IP 기반)
    - 검색/추적 API: 분당 10회
    - 트렌드 API: 분당 30회

### P2 - 중간

- [ ] **리소스 사용량 알림**
  - 현재: `mem_limit` 설정만 존재, 초과 시 OOM Kill
  - 개선:
    - Docker healthcheck 강화
    - 메모리/CPU 임계값 알림 (cAdvisor 또는 단순 스크립트)
    - 디스크 사용량 모니터링 (DB, Qdrant 데이터 증가)

- [x] **컨테이너 재시작 정책 최적화** ✅
  - 현재: `restart: unless-stopped` 일괄 적용
  - 개선:
    - 핵심 서비스 (backend, worker): `restart: always` + health check
    - 인프라 서비스 (postgres, qdrant, redis): `restart: always`
    - 보조 서비스 (beat): `restart: on-failure`

- [ ] **임베딩 품질 모니터링**
  - 현재: 배치 샘플링 평가만 존재 (`evaluate_batch_sample`)
  - 개선:
    - 클러스터링 품질 메트릭 (실루엣 스코어, 클러스터 간 거리)
    - 임베딩 차원 분포 시각화
    - API 비용 추적 (Azure OpenAI 토큰 사용량)

### P3 - 낮음

- [ ] **개발 환경 Docker 최적화**
  - 현재: 프로덕션과 개발 환경의 Dockerfile 공유 → 빌드 시간 20-30분
  - 개선:
    - 개발용 경량 Dockerfile 분리
    - multi-stage build 캐시 최적화
    - 의존성 레이어 분리 (requirements.txt → 소스 코드)

---

## 4. Product & 신규 기능

### P1 - 높음

- [x] **기사 스냅샷 저장** ✅
  - 현재: 기사 URL만 저장, 원문 삭제 시 접근 불가
  - 개선:
    - 크롤링 시 본문 HTML 아카이빙
    - 저장 용량 관리 (텍스트만 추출, 90일 보존)
    - 타임라인 뷰에서 스냅샷 미리보기

- [x] **사용자 인증 (기본)** ✅
  - ~~현재: 인증 없이 모든 기능 오픈~~
  - 구현: JWT 기반 관리자 대시보드 인증 (`/admin/login`, `.env`에서 `ADMIN_USERNAME`/`ADMIN_PASSWORD` 관리)
  - 미구현: 추적 이력 사용자별 관리, API 키 기반 외부 접근

- [x] **알림/웹훅 시스템** ✅
  - ~~현재: 추적 결과를 폴링으로만 확인~~
  - 구현: Discord 웹훅 연동 (`webhook.py`), NER fine-tuning 준비 완료/자동 트리거 알림
  - 미구현: 이메일 알림, Slack 연동, 키워드 모니터링 알림

### P2 - 중간

- [x] **트렌드 비교 분석** ✅
  - 현재: 단일 기간 트렌드만 표시
  - 개선:
    - 기간 간 비교 (24h vs 7d 변화량)
    - 카테고리별 트렌드 추이 차트
    - 언론사별 보도 성향 분석

- [x] **기사 북마크/컬렉션** ✅
  - 현재: 기사 저장 기능 없음
  - 개선:
    - 로컬 북마크 (localStorage)
    - 컬렉션 그룹핑
    - 북마크 기사 일괄 추적

- [ ] **RSS 피드 커스텀 설정**
  - 현재: 하드코딩된 카테고리 피드 + 고정 언론사 목록
  - 개선:
    - 관리자 UI에서 피드 URL 추가/수정
    - 피드별 수집 빈도 조절
    - 피드 상태 모니터링 (마지막 수집, 실패 횟수)

### P3 - 낮음

- [ ] **API 공개 & 문서화**
  - 현재: FastAPI auto-docs 존재하지만 미정리
  - 개선:
    - OpenAPI 스키마 정리
    - API 사용 가이드 작성
    - Rate limit/인증 안내

- [ ] **멀티 언어 뉴스 지원**
  - 현재: 한국어 뉴스만 대상
  - 개선:
    - 영어/일본어 Google News RSS 추가
    - 다국어 임베딩 모델 활용 (현재 모델이 multilingual 지원)
    - 크로스 언어 기사 유사도 비교

---

## 5. 코드 품질 & 리팩토링

### P1 - 높음

- [x] **Celery 이벤트 루프 보일러플레이트 통합** ✅
  - 파일: `backend/app/workers/tasks.py`
  - 현재: `asyncio.new_event_loop()` + `try/finally/close` 패턴이 5곳 반복
  - 개선: `run_async(coro)` 데코레이터 또는 헬퍼 함수로 통합

- [ ] **테스트 커버리지 확대**
  - 현재: 기본 통합 테스트만 존재
  - 개선:
    - 클러스터링 알고리즘 단위 테스트
    - API 엔드포인트 E2E 테스트
    - 크롤러 mock 테스트
    - 목표: 핵심 비즈니스 로직 80%+ 커버리지

### P2 - 중간

- [x] **프론트엔드 컴포넌트 테스트** ✅
  - 현재: vitest 설정 있으나 테스트 미작성
  - 개선:
    - 주요 페이지 컴포넌트 렌더링 테스트
    - 스토어 (Zustand) 상태 변경 테스트
    - SearchBar, ArticleList 인터랙션 테스트

- [x] **타입 안전성 강화** ✅
  - 현재: TypeScript strict 모드이나 일부 any 타입 존재
  - 개선:
    - API 응답 타입과 프론트엔드 타입 동기화 자동화
    - Zod 스키마 도입으로 런타임 타입 검증
    - 백엔드 Pydantic 스키마에서 프론트엔드 타입 자동 생성

---

## 구현 로드맵 (권장)

### Phase 1: 안정성 강화 (2-3주)
- P0 백엔드: 캐시 무효화 통합, Celery 동시실행 방지
- P0 인프라: DB 백업 자동화, Celery 모니터링 (Flower)
- P0 프론트엔드: 에러 바운더리 강화, 번들 최적화

### Phase 1.5: 보안 기반 (1-2주)
- P0 인프라: 도메인 확보 → HTTPS/SSL 설정 (DNS 전파 대기 포함)
- P1 인프라: Rate limiting 적용

### Phase 2: 사용자 경험 개선 (2-4주)
- P1 프론트엔드: 전파 트리 대량 노드, 모바일 UX, 트렌드 필터
- P1 백엔드: 페이지네이션, RSS 병렬화, Qdrant 배치 검색
- P1 인프라: 구조화된 로깅, CI/CD

### Phase 3: 기능 확장 (4-8주)
- P1 프로덕트: 기사 스냅샷, 기본 인증, 알림 시스템
- P2 전체: 토스트 시스템, 테마 토글, 테스트 확대, 타입 안전성

### Phase 4: 고도화 (8주+)
- P2-P3 프로덕트: 트렌드 비교, 북마크, RSS 커스텀
- P3 전체: PWA, 다국어, API 공개

---

## 구현 현황

> **마지막 업데이트**: 2026-02-20 (관리자 대시보드 + MLOps 고도화)
> **구현 완료**: 34/42 항목 (P0-P2 범위)

### 완료 요약

| 영역 | 완료 | 전체 | 비율 |
|------|------|------|------|
| Backend | 9 | 11 | 82% |
| Frontend | 8 | 8 | 100% |
| Infrastructure | 6 | 9 | 67% |
| Product | 5 | 7 | 71% |
| Code Quality | 3 | 4 | 75% |

### 미완료 사유

- **HTTPS/SSL**: 도메인 확보 및 DNS 설정 필요 (외부 의존)
- **API 페이지네이션**: 현재 데이터 규모(2500건)에서는 성능 이슈 없음, 향후 스케일 시 적용
- **테스트 커버리지**: 지속적 개선 항목
- **RSS 피드 커스텀**: 관리자 UI에서 피드 표시는 구현, 수정 기능은 미구현

### 주요 구현 내역

| 구현 항목 | 관련 파일 | 비고 |
|-----------|-----------|------|
| 캐시 무효화 통합 | `cache.py` | `invalidate_all_trend_caches()` 헬퍼 |
| Celery race condition 방지 | `tasks.py`, `cache.py` | Redis distributed lock |
| 이벤트 루프 보일러플레이트 | `tasks.py` | `run_async()` 헬퍼 |
| RSS 피드 병렬화 | `news_feed.py` | `asyncio.gather()` |
| Qdrant 배치 검색 | `vector_store.py`, `trend_clustering.py` | `search_similar_batch()` |
| JSONB 인덱스 | `004_add_metadata_category_index.py` | btree index |
| RFC 7807 에러 | `errors.py` | Problem Details 형식 |
| Azure OpenAI 재시도 | `azure_openai.py` | exponential backoff |
| ECharts tree-shaking | `echarts.ts`, `vite.config.ts` | 번들 분석 대시보드 |
| 에러 바운더리 강화 | `ErrorBoundary.tsx`, `errors.ts`, `api.ts` | 한국어 에러 메시지 + 재시도 |
| 트렌드 필터 | `TrendsPage.tsx` | 카테고리 + 언론사 필터 |
| 대량 노드 처리 | `PropagationGraph.tsx` | 50개 제한 + 토글 |
| 접근성 개선 | `DensityChart.tsx` 외 | `role="img"`, `aria-label` |
| 모바일 UX | `TimelineChart.tsx` 외 | 터치 지원, 반응형 높이 |
| 토스트 시스템 | `Toaster.tsx`, `useToastStore.ts` | 전역 알림 큐 |
| 빈 상태 UX | `EmptyState.tsx` | 재사용 가능 컴포넌트 |
| SSE 상태 표시 | `Header.tsx`, `useTrendStore.ts` | 연결/재연결/오프라인 |
| DB 백업 | `scripts/backup.sh` | pg_dump + Qdrant snapshot |
| Flower 모니터링 | `docker-compose.prod.yml` | 포트 15555 |
| 구조화된 로깅 | `logging_config.py` | JSON 형식 + request ID |
| CI/CD | `.github/workflows/ci.yml` | lint → test → build |
| Graceful degradation | `vector_store.py`, `cache.py`, `main.py` | 서비스별 fallback |
| Rate limiting | `nginx.prod.conf` | IP 기반 (10/30/60 rpm) |
| 재시작 정책 | `docker-compose.prod.yml` | 서비스별 차등 적용 |
| 기사 스냅샷 | `ArticleDetailPanel.tsx` | 미리보기 기능 |
| 기사 북마크 | `BookmarkButton.tsx`, `useBookmarkStore.ts` | localStorage 기반 |
| search_logs 정리 | `tasks.py` | 90일 기준 자동 정리 |
| 코사인 유사도 최적화 | `trend_clustering.py` | numpy dot/norm (10-50x) |
| 다크/라이트 테마 | `useTheme.ts`, `ThemeToggle.tsx`, `globals.css` | 3모드 (light/dark/system) |
| 트렌드 비교 분석 | `trends.py`, `TrendsPage.tsx`, `api.ts` | 기간별 비교 + 성장 토픽 |
| 프론트엔드 테스트 | `*.test.ts(x)` 11개 | 스토어/컴포넌트/스키마 테스트 |
| 타입 안전성 (Zod) | `schemas.ts`, `api.ts` | 런타임 타입 검증 통합 |

| 관리자 JWT 인증 | `auth.py`, `admin.py`, `LoginPage.tsx` | 단일 관리자 계정, 토큰 만료 |
| Discord 웹훅 | `webhook.py`, `tasks.py` | fine-tuning 준비 완료 알림 |
| 관리자 대시보드 7패널 | `admin.py`, 9개 프론트엔드 페이지 | 수집/MLOps/시스템/통계/로그/설정 |
| MLOps 파이프라인 시각화 | `admin.py`, `MLOpsPage.tsx` | 6단계 플로우 + 상태 뱃지 |
| 피드 출처 카드 | `admin.py`, `CollectionPage.tsx` | 카테고리 7 + 언론사 6 |
| MLOps 인라인 평가 | `admin.py`, `MLOpsPage.tsx` | 최근 24시간 GPT-5 평가 결과 |
| KST 예상 실행 시간 | `admin.py`, `MLOpsPage.tsx` | `_next_cron_run()` crontab→KST |
| 자동 Fine-tuning | `tasks.py` | 임계 도달 시 자동 트리거 (24h dedup) |
| 예측 대시보드 | `admin.py`, `MLOpsPage.tsx` | 현재 단계/수집률/예상 준비일 |
| Playwright e2e 테스트 | `admin-dashboard.spec.ts` | 4건 (collection + mlops 3건) |

### v1.1.0 배포 후 수정 사항

| 수정 항목 | 관련 파일 | 비고 |
|-----------|-----------|------|
| Qdrant null payload 가드 | `trend_clustering.py:319` | batch search 결과 null payload 방어 |
| 테마 토글 프로덕션 적용 | `index.html` | hardcoded `class="dark"`, `bg-gray-950` 제거 |
| Nginx 헬스체크 수정 | `docker-compose.prod.yml` | `localhost` → `127.0.0.1` (IPv6 해석 문제) |
| ThemeToggle 아이콘 전용 | `ThemeToggle.tsx` | 텍스트 라벨 제거, padding 최적화 |
| 카테고리 분포 패널 제거 | `Header.tsx` | 트렌드 페이지 다이어그램으로 대체 |
| 시간대별 수집량 차트 제거 | `TrendsPage.tsx` | 불필요 UI 정리 |
| 즉시 추적 동기화 최적화 | `articles.py`, `tasks.py`, `useTrackingStore.ts` | Celery 비동기 → API 동기 처리, Qdrant 벡터 재사용 (3-10s → ~1s) |
