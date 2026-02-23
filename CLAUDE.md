# News Origin - Claude Code Guide

## Project Overview
한국 뉴스 트렌드 분석 플랫폼. Google News RSS 크롤링 → 임베딩 생성 → 유사도 기반 기사 클러스터링 → 타임라인 시각화.

## Tech Stack
- **Backend**: FastAPI + SQLAlchemy (async) + Alembic + Celery + Pydantic Settings
- **Frontend**: React 19 + TypeScript + Vite + Zustand + Tailwind CSS + ECharts + React Flow (@xyflow/react)
- **Infra**: PostgreSQL 15 + Qdrant (vector DB) + Redis 7 + Nginx
- **Embedding**: Azure OpenAI `text-embedding-3-large` (1024차원, API 기반)
- **NER**: `klue/bert-base` 기반 키워드 추출 (kiwipiepy 폴백), MLOps fine-tuning 파이프라인
- **평가**: Azure OpenAI `gpt-5` (function calling 기반 NER 품질 평가 + 교정)

## Project Structure
```
backend/
  app/
    api/          # FastAPI 라우터 (articles, search, trends, timeline, health)
    config.py     # Pydantic Settings (환경변수 관리)
    core/         # 핵심 유틸 (db, qdrant, embedding)
    models/       # SQLAlchemy ORM 모델
    schemas/      # Pydantic 스키마
    services/     # 비즈니스 로직 (크롤링, 클러스터링)
    workers/      # Celery 태스크 + Beat 스케줄
  alembic/        # DB 마이그레이션
frontend/
  src/
    components/   # React 컴포넌트
    hooks/        # 커스텀 훅
    pages/        # 페이지 컴포넌트
    services/     # API 클라이언트
    stores/       # Zustand 상태관리
    types/        # TypeScript 타입
docker/           # nginx, redis, qdrant 설정 파일
```

## Commands
```bash
make dev              # 백엔드 + 프론트엔드 동시 실행
make dev-backend      # 백엔드만 (uvicorn --reload, :8000)
make dev-frontend     # 프론트엔드만 (vite, :5173)
make test             # 전체 테스트
make test-backend     # pytest
make test-frontend    # vitest
make lint             # pylint + eslint
make migrate          # alembic upgrade head
make migrate-create MSG="msg"  # 마이그레이션 생성
make docker-up        # 개발용 인프라 (postgres, qdrant, redis)
make docker-down      # 인프라 중지
```

## Docker Compose
- **개발**: `docker-compose.yml` - 포트: Postgres 15432, Qdrant 16333, Redis 16379
- **프로덕션**: `docker-compose.prod.yml` - Nginx :10880 (외부), 내부 포트만 사용
- 프로덕션 빌드: `docker compose -f docker-compose.prod.yml up -d --build`
- 프로덕션 로그: `docker compose -f docker-compose.prod.yml logs -f [service]`
- **Docker 내부 Python 실행 (CRITICAL)**: `docker compose exec <service> python3 -c "..."` — 반드시 `python3` 사용 (`python`은 시스템 Python을 가리킬 수 있어 모듈 미발견 오류 발생)

## Known Gotchas

### Celery 큐 이름 주의 (CRITICAL)
- `task_default_queue="celery"`가 `celery_app.py`에 명시되어 있음
- 이 설정이 없으면 Beat는 `default` 큐로 보내고 Worker는 `celery` 큐를 리스닝하여 태스크가 실행되지 않음
- 디버깅: `docker exec newsorigin-redis redis-cli KEYS '*'` → `LLEN default` vs `LLEN celery`로 확인

### Celery Beat 스케줄 파일
- Beat 시작 시 `/tmp/celerybeat-schedule.*` 잔여 파일이 있으면 스케줄 불일치 발생
- docker-compose.prod.yml에서 `rm -f` 후 Beat 시작하도록 설정됨

### 프로덕션 빌드 시간
- CUDA/PyTorch 패키지 포함으로 Docker 빌드에 20~30분 소요
- `--no-cache` 없이 빌드하면 캐시 활용 가능

### 환경변수
- `config.py`에서 Pydantic Settings로 관리, `.env` 파일 지원
- 개발/프로덕션 기본값이 다름 (DB 비밀번호, 포트 등)
- `APP_SECRET_KEY`는 프로덕션에서 반드시 변경

### datetime timezone (CRITICAL)
- **Beat 스케줄**: `timezone="Asia/Seoul"` — 모든 crontab 값은 KST 기준. `crontab(hour=11)`은 11:00 KST에 실행됨
- **DB 저장**: `datetime.now(timezone.utc)` — PostgreSQL 내부는 UTC 저장 (DB 비교/쿼리 일관성)
- **표시/출력**: 모든 사용자/관리자 시간은 KST — 프론트엔드 `toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })`, 이메일/리포트도 동일
- **`enable_utc=True`**: Celery 내부 메시지 타임스탬프만 UTC (crontab 해석에는 영향 없음, `timezone` 설정이 우선)
- **주의**: `_next_cron_run()` 등 스케줄 표시 함수도 KST 기준으로 계산해야 beat와 일치

### ECharts 차트 옵션 반드시 useMemo (CRITICAL)
- `ReactECharts`의 `option={{...}}` 인라인 객체 내 `formatter` 등 **함수가 포함되면** 매 렌더마다 새 참조 생성
- `echarts-for-react`는 `fast-deep-equal`로 비교하는데, **함수는 참조 비교**라 항상 "다름" 판정
- `notMerge` prop과 결합 시 매 렌더마다 차트를 완전 재생성 → 애니메이션 반복 재생
- **해결**: chart option과 onEvents를 반드시 `useMemo`로 감싸고, 실제 데이터 의존성만 deps에 포함
- Zustand store를 selector 없이 구독하면 무관한 필드 변경(SSE, recentArticles 등)에도 리렌더 발생 → 차트 갱신 트리거

## Crawling Pipeline
1. Celery Beat → `fetch_trending_news` (30분 간격)
2. Google News RSS 6개 카테고리 (headlines, politics, economy, society, tech, entertainment)
3. 카테고리당 최대 15건, 실행당 최대 50건
4. DB 중복 체크 → 본문 크롤링 → **BERT NER 키워드 추출** (제목에서 언론사 접미사 자동 제거) → **Azure 임베딩 생성** → PostgreSQL + Qdrant 저장
5. **임베딩 실패 시 DB 미저장 정책**: 임베딩 없는 기사는 벡터 검색/클러스터링이 불가하므로 DB에 저장하지 않음 (tasks.py v0.8.0)
6. **GPT-5 샘플링 품질 평가** (배치당 5건, `max_completion_tokens` 사용)
7. `cleanup_old_articles` 매일 03:00 (90일 이상 기사 삭제)

## NER MLOps Pipeline
- **목적**: GPT-5 평가 데이터로 BERT NER 모델을 점진적으로 개선하는 폐쇄 루프
- **데이터 수집**: 크롤링 배치마다 5건 샘플 평가 + 6시간 주기 30건 추가 수집
- **학습 제외 언론사**: `ner_excluded_publishers` 설정으로 AI 학습 금지 명시 언론사(한겨레 등) 기사를 학습 데이터 수집 및 평가 샘플에서 자동 제외
- **NER score 임계값**: `ner_score_threshold` (기본 0.25) — BERT NER v0003 모델의 score 분포(0.25~0.50)에 대응, 이전 하드코딩 0.5에서 설정화
- **per-title kiwipiepy fallback**: BERT가 빈 결과 반환 시 해당 제목만 kiwipiepy로 처리, `_ensure_kiwi()` 사용 (BERT 전역 상태 유지). `_load_kiwi()`는 BERT 완전 실패 시에만 사용
- **NER 상태 모니터링**: `check_worker_memory`에서 Redis `celery:worker:ner_status`에 BERT/kiwipiepy 로딩 상태 저장 (600s TTL)
- **GPT 평가 에이전트**: `ner_evaluation_agent.py` — Azure OpenAI function calling으로 구조화된 NER 교정
- **학습 데이터**: `ner_training_samples` 테이블에 BIO 태그 형식으로 축적
- **Fine-tuning**: 학습 데이터 임계치(`ner_training_min_samples`) 도달 시 `check_training_readiness`에서 자동 트리거
  - `trigger_bert_finetune` 태스크가 Docker SDK로 `newsorigin-finetune` 컨테이너를 detach 모드로 시작 → 워커 블로킹 없음
  - 수동 실행도 가능: `docker compose --profile finetune run finetune` (별도 컨테이너, CPU, ~2시간)
  - celery-worker/backend에 Docker 소켓 마운트 필요 (`/var/run/docker.sock`, `DOCKER_GID` 환경변수)
- **모델 관리**: `model_manager.py` — 심볼릭 링크 전환, quality gate (F1 비교), 롤백
- **모델 경로 우선순위**: `active 심볼릭 링크 > BERT_NER_MODEL_PATH > bert_model_name`
- **키워드 재추출**: 모델 교체 후 `reextract_keywords_batch` 태스크로 최근 7일 기사 재처리
- **DB 테이블**: `ner_training_samples`, `ner_model_versions` (Alembic 006), `deployment_insight` 컬럼 (Alembic 007), `original_entities` 컬럼 (Alembic 008)
- **Celery 스케줄**: `collect_ner_training_data` (6시간), `check_training_readiness` (매일 11:00 KST, 자동 fine-tuning 포함)
- **배포 인사이트**: 모델 승격 시 `mlops_insight.py`가 GPT-5로 품질 분석 인사이트 자동 생성 → `NerModelVersion.deployment_insight`에 저장
- **관리자 대시보드 (`/admin/mlops`)**: 파이프라인 7단계 시각화 (수집→평가→준비→Fine-tuning→배포→재추출→재클러스터링), finetune 컨테이너 실시간 상태/로그 모니터링, 인라인 평가 활동 (키워드 비교 확장행 + fallback 사유 + GPT reasoning), KST 예상 시간, 예측 대시보드, 품질 분석 차트 4종 + 배포 인사이트 카드, 섹션별 InfoBadge 툴팁
- **관리자 개요 (`/admin`)**: 서비스 상태 5종 (DB/Redis/Qdrant/Celery/NER 모델) + InfoBadge 역할 설명 툴팁, NER 모델 상태 (BERT ok/kiwipiepy warning/로딩 중)
- **시스템 모니터링 (`/admin/system`)**: 호스트 리소스 + 컨테이너별 메모리 사용량 (Docker SDK, ThreadPoolExecutor 병렬 수집), 프로그레스 바 + InfoBadge 설명

## Clustering Algorithm (v0.7.0)
- **그래프 기반 클러스터 병합**: Connected Components via BFS
- **임베딩 유사도 게이트**: cosine_sim >= 0.52 (CLUSTER_MERGE_EMB_THRESHOLD)
- **키워드 오버랩 게이트**: 정확 일치 또는 부분 문자열 매칭 (한국어 엔터티 변형 대응)
- **언론사명 키워드 제외**: Google News RSS 제목의 언론사 접미사(" - 매일경제" 등)를 키워드에서 자동 필터링
  - `keyword_extractor.py`: NER 추출 전 제목에서 언론사 접미사 제거 (`_strip_publisher_suffix`)
  - `trend_clustering.py`: 클러스터링 시 기사 집합에서 언론사명 수집 → 키워드 매칭/사유 생성에서 제외 (`_collect_publisher_names`, `_filter_keywords_data`)
- **최대 컴포넌트 제한**: MAX_COMPONENT_ARTICLES = 30 (메가 클러스터 방지)
- **기간별 일균등 샘플링** (v0.7.0): `_stratified_time_sample()` — 7d/30d에서 날짜별 버킷 균등 추출
  - 24h: 최신 500건 (기존 ORDER BY created_at DESC LIMIT)
  - 7d: 날짜당 ~143건 × 7일 = 1,000건, 30d: 날짜당 ~50건 × 30일 = 1,500건
  - `ARTICLES_LIMIT_BY_PERIOD`: 24h=500, 7d=1000, 30d=1500
  - `total_articles`: 별도 COUNT 쿼리로 기간 내 실제 전체 기사 수 표시
- **DB 인덱스**: `ix_articles_created_at` (Alembic 011) — 기간별 조회 성능 최적화
- **마이그레이션**: `python -m scripts.migrate_embeddings` (관계 초기화 + 재임베딩)

## 2단계 추적 시스템 (Tracking Pipeline)

### 1단계: 즉시 추적 (Instant)
- 사용자가 기사 확인 후 `confirm` 시 기본 동작
- 기존 DB/Qdrant 데이터에서 벡터 유사도 검색 (크롤링 없음)
- **동기 빠른 경로** (v1.1.1): 이미 임베딩이 있는 기사(`qdrant_point_id` 존재)는 API 핸들러에서 직접 처리
  - `_run_instant_sync()` in `articles.py`: Qdrant 벡터 조회 → 유사 검색 → DB 로드 → 타임라인 구성 → 응답
  - Celery 디스패치 + 폴링 오버헤드 제거 (3-10s → ~1s)
  - 실패 시 자동으로 Celery 비동기 fallback
- Celery 태스크 (fallback): `analyze_article_instant` (soft_time_limit=120s)
- 파이프라인: 원본 기사 로드 → NER 키워드 추출 → 임베딩 생성/재사용 → Qdrant 검색 → 타임라인 구성

### 2단계: Live 추적
- 즉시 추적 결과 화면에서 "Live 추적" 버튼으로 전환
- Google News RSS 실시간 크롤링 → 임베딩 → 유사도 분석 전체 파이프라인 실행
- Celery 태스크: `analyze_article_propagation` (soft_time_limit=600s)
- 새 TrackingRequest 생성 (tracking_type="live"), 기존 instant 결과 보존
- Live 결과 완료 시 프론트엔드가 자동으로 Live 타임라인으로 이동

### tracking_type 컬럼
- `TrackingRequest.tracking_type`: "instant" (기본값) | "live"
- Alembic 마이그레이션: `003_add_tracking_type.py`
- API 응답의 `tracking_type` 필드로 프론트엔드에서 UI 분기

## API Endpoints
- `POST /api/articles/track` - URL/제목으로 기사 검색 또는 크롤링
- `POST /api/articles/confirm` - 기사 확인 후 추적 시작 (instant 기본, tracking_type 선택 가능)
- `POST /api/articles/live-track` - 즉시 추적 → Live 추적 전환
- `GET /api/articles/{id}` - 기사 상세 조회
- `GET /api/timeline/{id}` - 기사 타임라인 조회
- `GET /api/timeline/{id}/status` - 추적 상태 폴링
- `GET /api/search/news` - 뉴스 검색
- `GET /api/trends/*` - 트렌드 분석
- `GET /api/admin/traffic` - 트래픽 통계 (시간별/일별, 상태코드, 엔드포인트, GeoIP, 에러)
- `GET /api/admin/reports` - 리포트 목록 (유형/등급 필터, 페이지네이션)
- `GET /api/admin/reports/{id}` - 리포트 상세 (content_json 포함)
- `GET /api/health` - 헬스체크
- `/policy` - 운영 정책 페이지 (프론트엔드 라우트)

## Request Logging (트래픽 수집)
- **수집 대상**: 실 사용자 트래픽만 (관리자/내부 트래픽 제외)
- **제외 경로**: `/api/admin/*`, `/api/health*`, `/assets/*`, `/favicon.ico`
- **제외 IP**: 사설/Docker/로컬호스트/예약 IP (`ipaddress` 모듈 `is_private|is_loopback|is_reserved`)
- **IP 추출 우선순위**: CF-Connecting-IP → X-Forwarded-For(첫 번째) → X-Real-IP → `request.client.host`
- **배치 INSERT**: `RequestLogWriter` — `deque(maxlen=10_000)` → 5초/50건마다 DB flush
- **GeoIP**: ip-api.com 배치 API, Redis 24시간 캐시
- **보존**: 90일 (기존 cleanup 태스크 연동)

## Admin Report System
- **정기 리포트**: `generate_weekly_report` (월요일 09:00 KST), `generate_monthly_report` (매월 1일 09:00 KST)
  - 기간 비교 (전기 대비 변동률), 일별 추이, 한국어 카테고리, 상위 언론사/엔드포인트
  - GPT-5 AI 내러티브: 비전문가 관리자 관점 운영 요약 자동 생성 (빈 응답 시 최대 2회 재시도)
- **비정기 리포트**: `check_system_alerts` (10분마다) — 에러율 급증, 트래픽 급증, 디스크/메모리 사용률
  - 카테고리별 대응 가이드 포함 (비전문가 관리자용)
- **이메일 발송**: SMTP HTML 템플릿, AI 운영 요약 포함, KST 시간 표시, 대시보드 링크, 쿨다운 60분
- **게시판 UI**: `/admin/reports` — 전통적 게시판 스타일 (목록 ↔ 상세 전환), 섹션별 전용 렌더러 (차트/프로그레스 바/테이블)
- **DB 테이블**: `admin_reports` (Alembic 010), content_json에 섹션별 통계 저장
- **설정**: `config.py` — `smtp_*`, `admin_email`, `alert_*_threshold`, `alert_cooldown_minutes`
- **report_generator.py**: 각 섹션(크롤링/트래픽/MLOps/시스템/에러) 독립 try/except + rollback
- **관리자 대시보드**: `/admin/traffic` — 에어리어 차트, GeoIP 분포, 상태코드, 엔드포인트 통계

## Host PC & Performance Constraints

### 호스트 사양 (CRITICAL - 모든 변경 시 고려)
- CPU: Intel i7-9750H (6코어/12스레드, 2.60GHz, 최대 4.5GHz) - MacBook Pro 2019
- RAM: 16GB
- GPU: AMD Radeon RX 5500M (CUDA 미지원) - BERT NER 모델은 CPU 전용, 임베딩은 Azure OpenAI API
- 사용자: 극소수

### Celery Worker 설정 주의 (CRITICAL)
- `--pool=solo` 필수: BERT NER 모델이 ~440MB로 프로세스당 차지
- 임베딩은 Azure OpenAI API로 전환되어 로컬 모델 로딩 없음 (메모리 ~600MB 절감)
- `prefork` pool이나 `concurrency > 1`로 변경하면 BERT 모델이 프로세스마다 로딩되어 OOM 발생
- `worker_max_tasks_per_child` 사용 금지: solo pool에서 프로세스 재시작 → 모델 재로딩 유발
- BERT NER 모델은 Celery 태스크에서만 사용됨, API 핸들러에서는 사용하지 않음

### Uvicorn Worker 설정
- `--workers 1` 사용: async 단일 워커로 충분 (사용자 극소수)
- 워커 수 증가 시 메모리 ~120MB/워커 추가 소요

### Docker mem_limit 설정 근거
| 컨테이너 | 한도 | 실사용 | 비고 |
|-----------|------|--------|------|
| celery-worker | 2048m | ~1.8GB (BERT NER v0003 + 배치 피크) | PyTorch ~300MB + BERT NER ~440MB + NER pipeline + 배치 오버헤드, 임베딩은 Azure API |
| qdrant | 512m | ~102m (현재) | 기사 누적 시 성장, 90일 보존 |
| backend | 384m | ~133m | 단일 uvicorn 워커 |
| celery-beat | 128m | ~48m | 스케줄러 전용 |
| postgres | 256m | ~110m | DB 크기 ~10MB, 캐시 사용량 증가 |
| redis | 64m | ~4m | maxmemory 32mb |
| nginx | 64m | ~4m | proxy_cache 포함 |
| finetune | 2048m | ~1.5GB (학습 시) | profiles: finetune, 필요 시만 실행 |
| frontend | 32m | ~10m | 정적 파일 서빙 |

### Nginx 캐싱 구조
- **proxy_cache**: trends API 4개 엔드포인트에 2~5분 TTL (nginx.prod.conf)
- **Redis 캐시**: 동일 엔드포인트에 TTL 1시간 (trends.py), 크롤 완료 시 삭제 후 즉시 재계산 워밍
- **이중 캐시**: Nginx(1ms 응답) → Redis(DB 쿼리 방지) 순서로 동작
- 프론트엔드: Nginx에서 직접 서빙 (`frontend_dist` 볼륨), /assets/ 1년 캐시
- 캐시 미적용: SSE(/api/trends/events), 쓰기 엔드포인트, 폴링
- **SSE 재연결**: 프론트엔드 Header.tsx에서 지수 백오프 자동 재연결 (1s → 최대 30s)

### DB 커넥션 풀
- backend pool_size=3 (base.py), worker pool_size=2 (tasks.py)
- 워커/프로세스 수 증가 시 pool_size도 조정 필요

## Code Conventions
- 파일 헤더에 버전/변경사항 docstring 포함
- `[BUSINESS LOGIC - DO NOT MODIFY]` 주석이 있는 코드는 수정 금지
- Backend: Python async/await, SQLAlchemy 2.0 스타일
- Frontend: 함수형 컴포넌트, Zustand 상태관리
- 커밋 메시지: `type: 한국어 설명` (fix, feat, refactor, docs 등)

## Deployment
- 배포 스크립트: `./scripts/deploy.sh {frontend|backend|all|full}`
- 상세 가이드: [docs/deployment.md](docs/deployment.md)

## Documentation Rules
- 모든 코드 변경 작업 완료 후, 관련 docs/ 문서를 찾아 업데이트할 것
- 새 기능/버그 수정은 [docs/changelog.md](docs/changelog.md)에 기록
- 배포 방법 변경 시 [docs/deployment.md](docs/deployment.md) 업데이트
- CLAUDE.md 본문은 핵심 참조만 유지, 상세 내용은 docs/ 하위 문서로 분리

## Linked Documents
- [docs/deployment.md](docs/deployment.md) — 배포 가이드 (deploy.sh, Docker Compose)
- [docs/changelog.md](docs/changelog.md) — 주요 변경 이력
- [docs/implementation-plan.md](docs/implementation-plan.md) — 구현 계획 (v1.0.0)
- [docs/infrastructure-p0-implementation.md](docs/infrastructure-p0-implementation.md) — 인프라 P0
- [docs/todo-enhancement.md](docs/todo-enhancement.md) — 개선 로드맵
