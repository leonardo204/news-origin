# Changelog

주요 변경사항 이력. 최신순 정렬.

---

## 2026-02-19

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
