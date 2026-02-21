# Changelog

주요 변경사항 이력. 최신순 정렬.

---

## 2026-02-22

### fix: Celery 헬스체크 Redis 하트비트 fallback + 트래픽 KST 그룹핑
- **Celery 헬스체크 개선**: `--pool=solo` 워커가 태스크 실행 중 `inspect().ping()` 응답 불가 → Redis 하트비트 fallback 추가
  - `check_worker_memory` 태스크(5분 주기)에서 `celery:worker:heartbeat` 키를 Redis에 기록 (TTL 600초)
  - 대시보드 overview 엔드포인트: inspect 실패 시 Redis 하트비트 존재 여부로 "정상" 판정
- **트래픽 KST 그룹핑**: 일별/시간별 쿼리에 `timezone('Asia/Seoul')` 적용 — UTC 기준 그룹핑으로 KST 날짜 불일치 해결
- **CLAUDE.md**: Docker 내부 Python 실행 시 `python3` 사용 규칙 명시
- **수정 파일**: `admin.py`, `tasks.py`, `CLAUDE.md`

### feat: 대시보드 개요 페이지 트래픽/MLOps 요약 추가 + Admin 차트 안정화
- **개요 페이지 트래픽 요약**: 오늘 요청수, 에러율(30일), 평균 응답시간(30일), 고유 방문자(30일)
- **개요 페이지 MLOps 요약**: 현재 모델/F1, 평균 품질, 학습 데이터 진행도, 학습 준비도 프로그레스 바
- **개요 섹션 순서 변경**: 기사 통계 → 트래픽 → MLOps → 크롤링 → 서비스 상태 → 시스템 리소스
- **백엔드 `/api/admin/overview`**: traffic(RequestLog 집계) + mlops(모델/학습 데이터) 요약 데이터 추가
- **React error #310 수정**: MLOpsPage, StatsPage, TrafficPage — `useMemo` 훅을 early return 앞으로 이동
- **ECharts 다크테마**: `dark-transparent` 커스텀 테마 등록, 전 관리자 차트에 동적 `theme` prop 적용
- **TrafficPage 일별 차트 재구축**: `useMemo` + `dataZoom` 슬라이더로 기간 탐색, 기존 period 탭 제거
- **수정 파일**: `admin.py`, `OverviewPage.tsx`, `MLOpsPage.tsx`, `StatsPage.tsx`, `TrafficPage.tsx`, `echarts.ts`

---

## 2026-02-21

### fix: Admin 대시보드 트래픽 SQL 오류 + 다크테마 차트 수정 + 모던 스타일 적용
- **SQL GROUP BY 오류 수정**: `admin.py` 트래픽 hourly 쿼리에서 `func.date_trunc("hour", ...)` → `literal_column("'hour'")` 변경 (asyncpg 파라미터 바인딩 불일치 해결)
- **다크테마 차트 가시성**: TrafficPage/MLOpsPage의 ECharts에 `echarts` prop + 동적 `theme` prop 추가, `backgroundColor: 'transparent'` 적용
- **모던 대시보드 스타일**: 전 관리자 페이지 차트를 현대적 스타일로 통일
  - TrafficPage: indigo 그라데이션 area 차트, 투명 배경, 부드러운 곡선 (smooth: 0.4), 도넛 센터 텍스트
  - StatsPage: CSS div 바 차트 → ECharts area 차트로 교체 (일별 기사 수집 추이)
  - MLOpsPage: 하드코딩 `theme="dark"` → 동적 테마 전환, 모든 차트 색상을 테마 변수로 교체
- **수정 파일**: `admin.py`, `TrafficPage.tsx`, `StatsPage.tsx`, `MLOpsPage.tsx`, `echarts.ts`

### fix: recent-articles 프론트엔드 페이지네이션 수정 + CPU 알림 추가
- **recent-articles 버그 수정**: 백엔드 `PaginatedRecentArticles` 응답(`{ items, total, offset, limit }`)을 프론트엔드가 flat array로 취급하던 버그 수정
  - `api.ts`: `data.items` 추출, `offset` 파라미터 전달, `{ items, total }` 반환
  - `useTrendStore.ts`: `recentArticlesTotal` 상태 추가, `loadMoreRecentArticles()` 액션 추가
  - `TrendsPage.tsx`: `.slice(0, 15)` 제거, 총 건수 표시, "더 보기 (N건 남음)" 버튼 추가
- **CPU 사용률 알림**: `alert_detector.py`에 `_check_cpu_usage` 추가 (90% warning, 95% critical, 60분 쿨다운)
  - `config.py`: `alert_cpu_threshold: int = 90` 설정 추가
- **todo-enhancement.md 정리**: P1 API 페이지네이션 ✅, P2 리소스 알림 ✅, 미완료 P3 항목 삭제
- **수정 파일**: `api.ts`, `useTrendStore.ts`, `TrendsPage.tsx`, `config.py`, `alert_detector.py`, `useTrendStore.test.ts`

### feat: 관리자 리포트 시스템 — 정기/비정기 리포트 + 이메일 발송 + GPT-5 내러티브
- **정기 리포트**: 매주 월요일/매달 1일에 자동 생성 (크롤링, 트래픽, MLOps, 시스템, 에러 통계)
  - 기간 비교 (이전 주/월 대비 변동률), 일별 추이, 한국어 카테고리 레이블
  - 상위 언론사 10위, 상위 엔드포인트 10위, 상태코드 분포
  - 시스템 리소스 상세 (CPU/메모리/디스크 총량·사용량·여유)
  - NER 모델 히스토리 + 품질 추이
- **GPT-5 AI 내러티브**: 수집된 통계를 GPT-5가 비전문가 관리자 관점으로 800자 이내 운영 요약 자동 생성
  - 빈 응답 시 자동 재시도 (최대 2회, GPT-5 reasoning 모델 간헐적 빈 content 대응)
- **비정기 리포트**: 10분마다 시스템 알림 체크 (에러율 급증, 트래픽 급증, 디스크/메모리 사용률) → 알림 리포트 자동 생성
  - 카테고리별 대응 가이드 (비전문가 관리자용 권장 조치)
- **이메일 발송**: SMTP HTML 템플릿 — AI 운영 요약 포함, KST 시간 표시, 대시보드 링크 (`https://news.zerolive.co.kr/admin/reports`)
- **게시판 UI**: 전통적인 게시판 스타일 (목록 ↔ 상세 전환)
  - 섹션별 전용 렌더러: 크롤링(카테고리 바 차트, 언론사 랭킹), 트래픽(상태코드 뱃지, 엔드포인트 테이블), MLOps(품질 추이 미니 차트, 모델 히스토리), 시스템(CPU/메모리/디스크 프로그레스 바), 에러(테이블), 알림(대응 가이드 카드)
- **DB 모델**: `admin_reports` 테이블 (report_type, title, summary, content_json, severity, email 상태)
- **Celery Beat**: `generate_weekly_report` (월 09:00 KST), `generate_monthly_report` (1일 09:00 KST), `check_system_alerts` (10분)
- **신규 파일**: `admin_report.py`, `email_sender.py`, `report_generator.py`, `alert_detector.py`, `010_add_admin_reports.py`, `ReportsPage.tsx`
- **수정 파일**: `config.py`, `tasks.py`, `beat_schedule.py`, `admin.py`, `adminApi.ts`, `App.tsx`, `AdminLayout.tsx`, `models/__init__.py`, `docker-compose.prod.yml`

### fix: celery-worker CORS_ORIGINS 환경변수 누락
- **문제**: `docker-compose.prod.yml`의 celery-worker에 `CORS_ORIGINS` 미설정 → 이메일 대시보드 링크가 `http://localhost:10080`으로 생성
- **수정**: celery-worker environment에 `CORS_ORIGINS=${CORS_ORIGINS:-}` 추가

### fix: 트렌드 카테고리 분포 차트 이중 렌더링 — 근본 수정
- **근본 원인**: `ReactECharts`의 `option={{...}}` 내 인라인 `formatter` 함수가 매 렌더마다 새 참조 생성 → `echarts-for-react`의 `fast-deep-equal` 비교 실패 → `notMerge`로 차트 완전 재생성 (애니메이션 2회 실행)
- **트리거**: `useTrendStore()` selector 미사용으로 `recentArticles`, SSE 상태 등 무관한 필드 변경에도 컴포넌트 리렌더
- **수정**: `categoryChartOption`과 `categoryChartEvents`를 `useMemo`로 메모이제이션 → 실제 데이터 변경 시만 차트 갱신
- **수정 파일**: `TrendsPage.tsx`

### feat: Admin 트래픽 대시보드 v2 — GeoIP + IP 필터링 + 차트 개선
- **GeoIP 분포**: ip-api.com 배치 API로 방문자 IP의 국가/도시 분포 집계, Redis 24시간 캐시 (`admin.py`)
- **사설 IP 필터링**: Docker 내부/로컬호스트/예약 IP 자동 제외 (`request_logger.py`: `_is_private_ip()`)
- **경로 필터링**: `/api/admin/*`, `/api/health*`, `/assets/*` 자동 제외 — 실 사용자 트래픽만 수집
- **클라이언트 IP 추출**: CF-Connecting-IP → X-Forwarded-For(첫 번째) → X-Real-IP → direct 우선순위 체인 (`logging_config.py`)
- **차트 개선**: 바 차트 → 그라데이션 에어리어 차트, 상태코드 도넛 중앙 합계, 국가별 플래그 이모지
- **수정 파일**: `admin.py`, `request_logger.py`, `logging_config.py`, `TrafficPage.tsx`

### feat: Admin 트래픽 대시보드
- **HTTP 요청 로그 수집**: FastAPI 미들웨어에서 요청 정보를 비동기 배치 큐에 적재 → 5초/50건마다 DB 일괄 INSERT (`request_logger.py`)
- **DB 모델**: `request_logs` 테이블 (method, path, status_code, duration_ms, client_ip, user_agent, created_at) + 3개 인덱스
- **API**: `/api/admin/traffic` — period(24h/7d/30d) 파라미터로 시간별/일별 트래픽, 상태코드 분포, 엔드포인트 통계, 최근 에러 반환
- **대시보드 UI**: ECharts 차트(시간별 듀얼축, 일별 스택 바, 상태코드 도넛) + 요약 카드 4개 + 엔드포인트/에러 테이블
- **Cleanup 연동**: 기존 `cleanup_old_articles` 태스크에서 90일 초과 request_logs 자동 삭제
- **신규 파일**: `request_log.py`, `request_logger.py`, `009_add_request_logs.py`, `TrafficPage.tsx`
- **수정 파일**: `models/__init__.py`, `logging_config.py`, `main.py`, `admin.py`, `tasks.py`, `adminApi.ts`, `App.tsx`, `AdminLayout.tsx`

### feat: RSS 정책 대응 — 한겨레 NER 학습 제외, 운영 정책, description 활용
- **한겨레 NER 학습 제외**: AI 학습 금지 명시 언론사(한겨레) 기사를 NER 학습 데이터 수집 및 GPT 평가 샘플에서 자동 제외 (`config.py`: `ner_excluded_publishers`, `tasks.py`, `evaluator.py`)
- **운영 정책 페이지**: `/policy` 경로에 서비스 목적, 콘텐츠 이용 방침, AI 학습 정책, 저작권 존중 등 명시, 연락처 이메일 포함 (`PolicyPage.tsx`, `App.tsx`, `Header.tsx`)
- **RSS description 수집**: 언론사 RSS의 description 필드를 파싱하여 크롤링 실패 시 summary 폴백으로 활용 (`news_feed.py`, `tasks.py`)
- **description 미리보기 UI**: 타임라인 카드에 summary 텍스트 표시 (`TimelineChart.tsx`, `timeline.py` 스키마/API)
- **수정 파일**: `config.py`, `tasks.py`, `evaluator.py`, `news_feed.py`, `timeline.py`(스키마+라우트), `App.tsx`, `Header.tsx`, `TimelineChart.tsx`, `types/index.ts`
- **신규 파일**: `PolicyPage.tsx`

### refactor: 추적 결과 화면 정리 + 헤더 레이아웃 변경
- **기사 목록 제거**: 추적 결과(TimelinePage)에서 ArticleList 컴포넌트 제거 (타임라인으로 충분)
- **정책 링크 위치 변경**: Header nav(추적, 트렌드) 우측의 테마토글·현황 영역으로 이동
- **트렌드 이중 로딩 수정**: StrictMode 이중 마운트 시 `loadArticleTrends()` 중복 호출 방지 (`useRef` 가드)
- **수정 파일**: `TimelinePage.tsx`, `Header.tsx`, `TrendsPage.tsx`

### fix: MLOps InfoBadge 추출 방식 설명 보정 + 평가 확장행 단일 열림
- **추출 방식 툴팁 보정**: kiwipiepy 100%가 "모델 로딩 문제"로만 설명되던 것을 "Fine-tuning 전 초기 상태(정상)" 케이스 추가
- **확장행 단일 열림**: 인라인 평가 테이블에서 행 클릭 시 기존 열린 행은 자동 접힘 (한 번에 하나만 열림)
- **인라인 평가 InfoBadge 설명 추가**: 키워드 비교 기능 안내 + Fine-tuning 효과 설명 2줄 추가

### feat: MLOps 대시보드 — InfoBadge 툴팁 + 키워드 비교 확장행
- **InfoBadge 툴팁 (`?` 아이콘)**: MLOps 대시보드 10개 섹션(파이프라인, 학습 데이터, 품질 추이, 엔터티 오류, 모델 성능, 추출 방식, 배포 인사이트, 인라인 평가, 설정 3종)에 hover 시 설명 툴팁 표시 (`InfoBadge.tsx` 신규)
- **키워드 비교 확장행**: 인라인 평가 활동 테이블에서 행 클릭 시 "현재 모델 추출 vs GPT-5 교정" 엔터티 비교 표시, 엔터티 유형별 색상 코딩 (PS/OG/LC/DT/TI/QT)
- **`original_entities` 컬럼 추가**: `ner_training_samples` 테이블에 평가 시점 원본 추출 엔터티 저장 (Alembic 008)
- **수정 파일**: `MLOpsPage.tsx`, `admin.py`, `ner_training.py`, `ner_training_pipeline.py`, `tasks.py`
- **신규 파일**: `InfoBadge.tsx`, `008_add_original_entities.py`

### fix: 타임라인 기원 기사 정렬 — 백엔드 쿼리 수정
- **문제**: 동일 날짜 기사가 많을 때 기원(origin) 기사가 타임라인 중간에 위치
- **수정**: `timeline.py` 쿼리에 `TimelineEntry.is_origin.desc()` 1차 정렬 추가하여 기원 기사가 항상 첫 번째에 위치
- **수정 파일**: `backend/app/api/routes/timeline.py`

### fix: 6건 버그 수정 및 UX 개선
- **추출 방식 0/0 비율 버그**: BERT NER 0건/kiwipiepy 0건일 때 kiwipiepy가 100%로 표시되던 버그 수정 (`MLOpsPage.tsx`)
- **대시보드 로그 KST 시간**: 로그 뷰어 타임스탬프를 UTC ISO → KST (`MM/DD HH:MM:SS KST`) 형식으로 변경 (`admin.py`)
- **트렌드 카테고리 차트 이중 렌더링**: 탭 진입 시 `loadArticleTrends()` 중복 호출 방지, 기존 데이터가 있으면 재사용 (`TrendsPage.tsx`)
- **타임라인 기원 기사 정렬**: 기사 목록 + 타임라인 차트에서 기원(origin) 기사가 정렬과 무관하게 항상 맨 위에 위치하도록 수정 (`ArticleList.tsx`, `TimelineChart.tsx`)
- **전파 트리 미니맵 제거 + 기원 포커스**: 흰색으로 렌더되던 MiniMap 삭제, 초기 뷰를 기원 노드 중심으로 배율 조정 (`PropagationGraph.tsx`)
- **홈→트렌드 토픽 연동**: 홈에서 실시간 트렌드 토픽 클릭 시 트렌드 탭에서 해당 토픽이 선택+스크롤 이동되도록 구현 (`TrendsPage.tsx`, `HomePage.tsx`)
- **period/data 정합성**: URL period 파라미터 변경 시 캐시된 데이터 무효화하여 불일치 방지

### fix: NER MLOps 파이프라인 — 학습 데이터 수집 정상화
- **GPT-5 function calling JSON 추출 개선**: reasoning 모델이 tool_calls 대신 텍스트로 응답할 때 코드블록/전체 JSON/내장 JSON 3단계 추출 (`azure_openai.py`)
- **tool_choice 호환성**: GPT-5 reasoning 모델과 호환되도록 `tool_choice`를 forced function → `"auto"`로 변경, 프롬프트에 JSON 폴백 형식 안내 (`ner_evaluation_agent.py`)
- **이중 GPT-5 호출 제거**: `save_evaluation_results`에서 `evaluate_and_correct()` 재호출 삭제, `evaluate_batch_sample` 결과의 `corrected_entities` 직접 재사용 (`ner_training_pipeline.py`)
- **과도한 품질 게이트 제거**: 초기 평가 점수 0.7 미만 필터가 모든 샘플을 차단하던 문제 수정 (평가 실패만 스킵)
- **async event loop 충돌 수정**: Celery async task 내에서 `asyncio.new_event_loop()` 호출 시 "Cannot run the event loop while another loop is running" 에러 → `save_evaluation_results`를 async로 전환 (`ner_training_pipeline.py`, `tasks.py`)
- **결과**: 매 크롤링 배치(30분)마다 5건씩 학습 데이터 정상 축적 (0건 → 6건 확인)

---

## 2026-02-20

### feat: MLOps 품질 분석 대시보드 + 배포 시 자동 인사이트
- **품질 추이 차트**: 최근 30일 일별 NER 평균 품질 점수 + 평가 건수 혼합 차트 (ECharts Line+Bar)
- **엔터티 유형별 오류 분포**: GPT-5 교정 엔터티의 type별 도넛 차트 (PS/OG/LC/DT/TI/QT)
- **모델 성능 비교**: 모델 버전별 F1 점수 바 차트, 활성 모델 강조
- **추출 방식 비율**: BERT NER vs kiwipiepy 비율 프로그레스 바
- **배포 인사이트**: 모델 승격 시 GPT-5가 축적 데이터(품질 추이, 엔터티 오류, 모델 히스토리, 평가 사유)를 분석하여 인사이트 자동 생성 → DB 저장 → 대시보드 표시
- **DB 변경**: `ner_model_versions.deployment_insight` 컬럼 추가 (Alembic 007)
- **신규 파일**: `mlops_insight.py` (GPT-5 인사이트 생성 서비스)
- **수정 파일**: `admin.py` (v0.5.0), `ner_training.py`, `finetune_bert_ner.py`, `MLOpsPage.tsx`, `admin-dashboard.spec.ts`

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
