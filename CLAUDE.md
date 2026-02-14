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

## Code Conventions
- 파일 헤더에 버전/변경사항 docstring 포함
- `[BUSINESS LOGIC - DO NOT MODIFY]` 주석이 있는 코드는 수정 금지
- Backend: Python async/await, SQLAlchemy 2.0 스타일
- Frontend: 함수형 컴포넌트, Zustand 상태관리
- 커밋 메시지: `type: 한국어 설명` (fix, feat, refactor, docs 등)
