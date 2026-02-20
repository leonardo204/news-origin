# Changelog

주요 변경사항 이력. 최신순 정렬.

---

## 2026-02-20

### fix: 트렌드 탭 UX 개선 — 상태 초기화, 비교 상태바, 이중 로딩 방지
- **탭 진입 시 상태 초기화**: 트렌드 탭을 나갔다가 다시 들어올 때 `trendView`, `period`, `expandedClusterId`를 기본값으로 리셋 (Zustand `resetView()` 추가)
- **비교 로딩 상태바**: '비교' 탭 클릭 시 period 전환과 동일한 상단 프로그레스 바 표시 (`isLoadingComparison` 조건 추가)
- **카테고리 분포 이중 로딩 방지**: 마운트 시 2개 `useEffect`(데이터 로딩 + URL period 동기화)를 1개로 통합하여 `loadArticleTrends()` 1회만 호출
- **`loadComparison` 의존성 수정**: `handleSetTrendView`, `handleSetPeriod`의 dependency array에 `loadComparison` 추가하여 stale closure 방지
- **수정 파일**: `TrendsPage.tsx`, `useTrendStore.ts`

### feat: MLOps 대시보드 고도화 — 인라인 평가, KST 예상 시간, 자동 Fine-tuning, 예측 대시보드
- **인라인 평가 활동 카드**: 크롤링 배치마다 실행되는 GPT-5 NER 평가 결과를 최근 24시간 테이블로 시각화 (품질 점수, 추출 방식, 수집 시각)
- **KST 예상 실행 시간**: 모든 MLOps 스케줄 항목에 한국시간(UTC+9) 다음 실행 시각 표시, `_next_cron_run()` 유틸로 crontab 패턴에서 KST 변환
- **자동 Fine-tuning**: `check_training_readiness` 태스크에서 학습 데이터 임계치 도달 시 `trigger_bert_finetune.delay()` 자동 호출 (24시간 내 중복 방지)
- **예측 대시보드**: 현재 단계(데이터 수집 중/fine-tuning 대기), 일일 수집률, 예상 준비 완료일, 다음 자동 트리거 조건을 배너로 표시
- **수정 파일**: `admin.py` (v0.4.0), `tasks.py`, `MLOpsPage.tsx`

### feat: 관리자 대시보드 — 피드 출처 + MLOps 스케줄링 시각화
- **수집 관리 페이지**: 카테고리 RSS 피드 7개 + 언론사 RSS 피드 6개 출처 카드 추가 (URL, 피드당 수집 한도 표시)
- **MLOps 페이지**: 6단계 파이프라인 시각화 (수집 → 평가 → 준비 → 학습 → 배포 → 재추출)
  - 단계별 상태 뱃지 (진행중/완료/대기/수집중), 프로그레스 바, 예상 소요일
  - 학습 데이터 진행률 요약 바 (unused/target)
- **MLOps 스케줄 테이블**: 5개 작업의 주기 및 상세 정보 표시
- **백엔드**: `/api/admin/crawl`에 `feed_sources`, `/api/admin/mlops`에 `schedule`+`pipeline` 필드 추가
- **수정 파일**: `admin.py`, `CollectionPage.tsx`, `MLOpsPage.tsx`

### fix: 관리자 대시보드 데이터 누락 및 undefined 수정
- **JSONB GROUP BY 오류 수정**: `Article.metadata_["category"]` JSONB 컬럼의 GROUP BY에서 parameterized query 불일치로 PostgreSQL 에러 발생 → `literal_column` 사용으로 해결
  - `/api/admin/crawl`: category_stats, publisher_stats, recent_articles, daily_counts 모두 빈 배열 반환 → 정상 데이터 반환
  - `/api/admin/stats`: articles_by_category, top_publishers 빈 배열 반환 → 정상 데이터 반환
- **쿼리 독립 실행**: `/crawl`, `/stats` 엔드포인트의 단일 try/except 블록을 각 쿼리별로 분리하여 한 쿼리 실패 시 다른 데이터까지 빈 값이 되는 연쇄 장애 방지
- **크롤링 상태 필드명 수정**: `crawl.last_run`이 항상 null — `cs.get("updated_at")` → `cs.get("started_at")` (캐시 실제 필드명과 일치)
- **설정 페이지 undefined 수정** (백엔드 + 프론트엔드):
  - `crawling.max_articles_per_run`: 누락 → `MAX_ARTICLES_PER_RUN` (90) 추가
  - `crawling.retention_days`: `system` 섹션에만 있던 값을 `crawling`에도 추가
  - `mlops.max_versions`: `max_model_versions` → `max_versions`로 필드명 통일
  - `system.debug`: 백엔드에 없는 필드 → `system.retention_days` 표시로 대체
  - 프론트엔드 `SettingsData` 인터페이스를 백엔드 실제 응답과 정합성 일치

### feat: 관리자 대시보드 (`/admin`)
- **목적**: 수집현황, MLOps, 시스템 자원, 통계, 로그, 설정을 한눈에 모니터링하는 관리자 콘솔
- **인증**: JWT 기반 단일 관리자 계정 (`.env`에서 `ADMIN_USERNAME`, `ADMIN_PASSWORD` 관리)
- **백엔드**: `/api/admin/*` 9개 엔드포인트 (login, verify, overview, crawl, mlops, system, stats, logs, settings)
  - 인메모리 로그 링 버퍼 (최근 1000건), Celery inspect 연동, psutil 시스템 모니터링
- **프론트엔드**: React 7개 페이지 + 사이드바 레이아웃 + 로그인 페이지
  - 코드 스플릿: 각 페이지 5-10KB gzip
  - 다크/라이트 모드 전환, 30초 자동 새로고침
- **읽기 전용**: 설정 변경 기능 없음 (모니터링 전용)
- **신규 파일**: `auth.py`, `routes/admin.py`, `adminApi.ts`, `useAdminStore.ts`, 9개 페이지 컴포넌트
- **수정 파일**: `config.py`, `requirements.txt`, `main.py`, `App.tsx`, `docker-compose.prod.yml`, `.env.example`

### feat: NER 키워드 추출 품질 개선 MLOps 파이프라인
- **목적**: BERT NER 모델("윤석열" → "윤석"만 추출 등) 품질을 GPT-5 평가 데이터로 점진 개선하는 폐쇄 루프 구축
- **Phase 1 — 학습 데이터 수집**:
  - GPT-5 function calling 기반 NER 평가 에이전트 (`ner_evaluation_agent.py`) — 파싱 실패 제거
  - BIO 태그 변환 + DB 영속화 파이프라인 (`ner_training_pipeline.py`)
  - 크롤링 배치 완료 시 평가 결과 자동 DB 저장 (기존 로그만 기록 → DB 축적)
  - 6시간 주기 추가 학습 데이터 수집 태스크 (`collect_ner_training_data`)
- **Phase 2 — Fine-tuning + 배포**:
  - HuggingFace Trainer 기반 fine-tuning 스크립트 (`scripts/finetune_bert_ner.py`, CPU, epochs=3)
  - 별도 Docker 컨테이너 (`docker compose --profile finetune run finetune`)
  - 모델 버전 관리자 (`model_manager.py`) — 심볼릭 링크 전환, quality gate, 롤백
  - 모델 교체 후 최근 7일 기사 키워드 재추출 태스크 (`reextract_keywords_batch`)
- **DB 스키마**: `ner_training_samples`, `ner_model_versions` 테이블 추가 (Alembic 006)
- **설정**: `config.py`에 MLOps 관련 6개 설정 추가
- **기존 기능 영향 없음**: 서비스 중단 없이 운영, fine-tuning은 별도 컨테이너
- **수정 파일**: 6개 신규 + 8개 수정 (상세는 CLAUDE.md 참조)

---

## 2026-02-19

### fix: 트렌드 페이지 UX 개선 + 현황 패널 용어 변경
- 트렌드 period 전환 시 기존 콘텐츠 유지 + 프로그레스 바 표시 (깜빡임 제거)
- 언론사 필터 ↔ 카테고리 필터 위치 교환, 언론사 필터와 period 셀렉터 수평 정렬
- 현황 패널: '크롤링' → '수집상태', '총 추적' 삭제, '마지막 크롤링' → '마지막 업데이트'

### fix: SSE 연결 상태 표시 개선 — 짧은 끊김 무시
- **문제**: SSE 잠깐 끊길 때마다 "연결 끊김"이 표시되어 사용자 신뢰도 저하
- **수정**: 5초 이상 끊겨 있을 때만 'offline' 상태 표시, 빠른 재연결 시 사용자에게 노출하지 않음 (`Header.tsx`)

### fix: 트렌드 카드 last_seen 시간 표시 오류 + 색상 바 높이
- **문제 1**: `last_seen`이 `published_at`(RSS 발행일, 시간 없이 00:00:00Z)을 사용하여 모든 카드가 동일한 "N시간 전"으로 표시됨
- **수정**: `last_seen`을 `created_at`(실제 수집 시각) 기준으로 변경 (`trend_clustering.py`)
- **문제 2**: 홈 트렌드 카드가 3열 그리드에서 높이가 다를 때 왼쪽 카테고리 색상 바가 카드 전체 높이를 채우지 못함
- **수정**: `CardContent`에 `h-full` 추가 (`HomePage.tsx`)

### fix: 누락된 ORM 모델 파일 추가 + .gitignore 수정
- **문제**: `.gitignore`의 `models/` 규칙(ML 모델 캐시용)이 `backend/app/models/` 디렉토리까지 무시하여 `base.py`, `article.py`, `search_log.py`, `__init__.py` 4개 파일이 git에 커밋되지 않았음
- **수정**: `models/` → `*.bin`, `*.pt`, `*.onnx`, `*.safetensors` 확장자 기반으로 변경
- 모델 파일 4개 커밋 추가

### infra: 호스트 마이그레이션 완료 (i3-2310M → i7-9750H)
- 기존 호스트(Intel i3-2310M, 3.8GB RAM)에서 신규 호스트(Intel i7-9750H, 16GB RAM)로 이전
- PostgreSQL 4325 articles, Qdrant 4766 vectors 복원 완료
- CLAUDE.md 호스트 사양 및 실사용 메모리 수치 업데이트

---

## 2026-02-18

### fix: 클러스터 키워드에서 언론사명 제외 — 품질 개선
- **문제**: Google News RSS 제목에 포함된 언론사명(" - 매일경제" 등)이 NER 키워드로 추출되어 클러스터 사유에 "매일경제" 같은 무의미한 키워드가 표시됨
- **수정 파일**:
  - `backend/app/core/trend_clustering.py`: 클러스터링 시 언론사명 자동 수집(`_collect_publisher_names`) → 키워드 매칭/사유 생성에서 제외(`_filter_keywords_data`)
  - `backend/app/services/keyword_extractor.py`: NER 추출 전 제목에서 언론사 접미사 제거(`_strip_publisher_suffix`)
- 기존 DB 기사(언론사명 포함 키워드)와 신규 기사(제거됨) 모두 대응

### fix: Zod 스키마에 cluster_reason 필드 추가 — 뱃지 미표시 수정
- **문제**: `ClusterArticleSchema`에 `cluster_reason` 필드가 없어 Zod `safeParse()`가 해당 필드를 strip → 프론트엔드에서 뱃지 미표시
- **수정 파일**: `frontend/src/lib/schemas.ts`
- `cluster_reason: z.string().nullable().optional()` 추가

### feat: 클러스터 기사 목록 UI 개선 — 대표 뱃지 + 공통점 인라인
- **수정 파일**: `frontend/src/pages/TrendsPage.tsx`
- 대표 기사에 "대표" 뱃지, 사용자 선택 기사에 "선택" 뱃지 표시
- `cluster_reason` 인라인 표시 (공통 키워드/유사도 사유)
- 트렌드 페이지 이탈 시 선택 상태 초기화 (`useTrendStore.resetSelectedArticle`)

### feat: 전파트리 React Flow 마이그레이션 + 카드형 디자인
- **변경**: `@antv/g6` → `@xyflow/react` (React Flow v12) + `@dagrejs/dagre` 전환
- **수정 파일**: `frontend/src/components/visualization/PropagationGraph.tsx` (전면 재작성)
- dagre LR 레이아웃 + serpentine 행 줄바꿈 (MAX_COLS_PER_ROW=4)
- 커스텀 카드형 노드: 흰색 배경 + 좌측 라이프사이클 컬러바 + 그림자
- 제목 2줄 허용 (truncate 50자), 유사도 배지, 라이프사이클 라벨 표시
- fitView (maxZoom 0.8) + panOnScroll + 확대/축소 지원
- MiniMap/Controls 제거 (사용자 피드백 반영)
- 번들 사이즈 83% 감소 (vendor-g6 1,353KB → PropagationGraph 229KB)

### feat: 전파트리 모달 풀사이즈
- **수정 파일**: `frontend/src/pages/TimelinePage.tsx`
- 모달 `sm:h-[95vh] sm:w-[97vw]` (max-w/max-h 제한 제거)

### fix: 트렌드 기간 전환 504 타임아웃 — 캐시 워밍 도입
- **문제**: 7d/30d 트렌드 클러스터링이 최대 48초 소요 → nginx 60s timeout → 504
- **근본 원인**: 크롤링 후 캐시 삭제만 하고 재계산하지 않아 다음 사용자 요청 시 on-demand 계산
- **수정 파일**: `backend/app/workers/tasks.py`
  - 크롤링 완료 후 24h/7d/30d 트렌드 캐시 미리 계산하여 Redis 저장 (TTL 1시간)
  - 사용자 요청 시 항상 캐시 히트 (<10ms)
- **안전장치**: `docker/nginx/nginx.prod.conf` proxy_read_timeout 60s→180s, `frontend/src/services/api.ts` axios timeout 30s→120s

### fix: Celery 크롤링 16시간 중단 — stale Redis lock 수정
- **문제**: `fetch_trending_news` 태스크가 매 실행 시 `already_running`으로 skip
- **원인**: Celery 태스크마다 새 이벤트 루프를 생성하는데, 이전 루프의 Redis 클라이언트(`_redis` 전역변수)가 stale 상태로 남아 `_exec_redis` 재연결 시 `SET NX`가 실패
- **추가 버그**: `finally` 블록에서 락을 획득하지 않은 태스크도 무조건 `release_task_lock` 호출
- **수정 파일**: `backend/app/workers/tasks.py`
  - 태스크 시작 시 `_reset_redis()` 호출하여 stale 연결 선제 제거
  - `lock_acquired = False` 안전한 기본값
  - `if lock_acquired:` 조건으로 락을 획득한 경우에만 해제

### feat: 로고 클릭 시 data refresh
- **수정 파일**: `frontend/src/components/layout/Header.tsx`
- 로고 클릭 시 `loadStats`, `loadCrawlStatus`, `loadArticleTrends`, `loadRecentArticles` 호출

### feat: 홈 실시간 트렌드 카테고리별 1개 + UX 개선
- **수정 파일**: `frontend/src/pages/HomePage.tsx`
- 카테고리별 대표 1개 클러스터만 표시 (기존 상위 9개 → 카테고리별 필터)
- 카드 좌측 카테고리 색상 바, 제목 크기 확대, 대표 언론사 표시

### fix: 트렌드 페이지 period 필터 즉시 반영
- **수정 파일**: `frontend/src/stores/useTrendStore.ts`
- `setPeriod`에서 기존 데이터 클리어 + `isLoading=true` 강제 설정
- 기존: 이전 period 데이터가 남아 변화 체감 불가 → 수정: skeleton UI 표시 후 새 데이터 렌더링

### docs: CLAUDE.md 구조화 + 하위 문서 분리
- CLAUDE.md에 Deployment, Documentation Rules, Linked Documents 섹션 추가
- `docs/deployment.md` 신규 (배포 가이드)
- `docs/changelog.md` 신규 (변경 이력)
