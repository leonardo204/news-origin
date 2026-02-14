# News Origin - Claude Code Guide

## Project Overview
한국 뉴스 트렌드 분석 플랫폼. Google News RSS 크롤링 → 임베딩 생성 → 유사도 기반 기사 클러스터링 → 타임라인 시각화.

## Tech Stack
- **Backend**: FastAPI + SQLAlchemy (async) + Alembic + Celery + Pydantic Settings
- **Frontend**: React 19 + TypeScript + Vite + Zustand + Tailwind CSS + ECharts + @antv/g6
- **Infra**: PostgreSQL 15 + Qdrant (vector DB) + Redis 7 + Nginx
- **Embedding**: `paraphrase-multilingual-mpnet-base-v2` (768차원, sentence-transformers)

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

### datetime timezone
- 모든 datetime은 UTC 기준 (`enable_utc=True`)
- 프론트엔드에서 KST 변환 표시
- Beat 스케줄의 crontab은 UTC 기준 (timezone="Asia/Seoul" 설정으로 보정)

## Crawling Pipeline
1. Celery Beat → `fetch_trending_news` (30분 간격)
2. Google News RSS 6개 카테고리 (headlines, politics, economy, society, tech, entertainment)
3. 카테고리당 최대 15건, 실행당 최대 50건
4. DB 중복 체크 → 본문 크롤링 → 임베딩 생성 → PostgreSQL + Qdrant 저장
5. `cleanup_old_articles` 매일 03:00 (90일 이상 기사 삭제)

## API Endpoints
- `POST /api/articles/track` - URL로 기사 추적 시작
- `POST /api/articles/confirm` - 크롤링 결과 확인/저장
- `GET /api/timeline/{id}` - 기사 타임라인 조회
- `GET /api/search/news` - 뉴스 검색
- `GET /api/trends/*` - 트렌드 분석
- `GET /api/health` - 헬스체크

## Host PC & Performance Constraints

### 호스트 사양 (CRITICAL - 모든 변경 시 고려)
- CPU: Intel i3-2310M (2코어/4스레드, 2.10GHz) - 2011년형 저사양
- RAM: 3.8GB (동일 호스트에서 Outline Wiki도 운영)
- GPU: 없음 - 임베딩 모델은 CPU 전용
- 사용자: 극소수

### Celery Worker 설정 주의 (CRITICAL)
- `--pool=solo` 필수: 임베딩 모델이 1061MB (278M 파라미터)로 프로세스당 ~1GB 차지
- `prefork` pool이나 `concurrency > 1`로 변경하면 모델이 프로세스마다 로딩되어 OOM 발생
- `worker_max_tasks_per_child` 사용 금지: solo pool에서 프로세스 재시작 → 모델 재로딩 유발
- 임베딩 모델은 Celery 태스크에서만 사용됨, API 핸들러에서는 사용하지 않음

### Uvicorn Worker 설정
- `--workers 1` 사용: async 단일 워커로 충분 (사용자 극소수)
- 워커 수 증가 시 메모리 ~120MB/워커 추가 소요

### Docker mem_limit 설정 근거
| 컨테이너 | 한도 | 실사용 | 비고 |
|-----------|------|--------|------|
| celery-worker | 1280m | ~1100m (모델 로딩 후) | 임베딩 모델 1061MB + 오버헤드 |
| qdrant | 512m | ~75m (현재) | 기사 누적 시 성장, 90일 보존 |
| backend | 384m | ~130m | 단일 uvicorn 워커 |
| celery-beat | 128m | ~46m | 스케줄러 전용 |
| postgres | 128m | ~28m | DB 크기 ~10MB |
| redis | 64m | ~5m | maxmemory 32mb |
| nginx | 64m | ~4m | proxy_cache 포함 |
| frontend | 32m | ~5m | 정적 파일 서빙 |

### Nginx 캐싱 구조
- **proxy_cache**: trends API 4개 엔드포인트에 2~5분 TTL (nginx.prod.conf)
- **Redis 캐시**: 동일 엔드포인트에 10~30분 TTL (trends.py), 크롤 완료 시 명시적 삭제
- **이중 캐시**: Nginx(1ms 응답) → Redis(DB 쿼리 방지) 순서로 동작
- 프론트엔드: Nginx에서 직접 서빙 (`frontend_dist` 볼륨), /assets/ 1년 캐시
- 캐시 미적용: SSE(/api/trends/events), 쓰기 엔드포인트, 폴링

### DB 커넥션 풀
- backend pool_size=3 (base.py), worker pool_size=2 (tasks.py)
- 워커/프로세스 수 증가 시 pool_size도 조정 필요

## Code Conventions
- 파일 헤더에 버전/변경사항 docstring 포함
- `[BUSINESS LOGIC - DO NOT MODIFY]` 주석이 있는 코드는 수정 금지
- Backend: Python async/await, SQLAlchemy 2.0 스타일
- Frontend: 함수형 컴포넌트, Zustand 상태관리
- 커밋 메시지: `type: 한국어 설명` (fix, feat, refactor, docs 등)
