# News Origin - Host Migration Guide

> 이 문서는 Claude Code가 새 호스트에서 마이그레이션을 수행할 때 참조하는 context 문서입니다.

## 마이그레이션 개요

News Origin 서비스를 호스트 A(기존) → 호스트 B(신규)로 이전합니다.

### 아키텍처 요약
- **Docker Compose 기반** 프로덕션 (docker-compose.prod.yml)
- **8개 컨테이너**: postgres, qdrant, redis, backend, celery-worker, celery-beat, flower, frontend, nginx
- **3개 영구 데이터 볼륨**: `postgres_data`, `qdrant_data`, `redis_data`
- **1개 빌드 볼륨**: `frontend_dist` (빌드 시 자동 생성, 백업 불필요)

### 마이그레이션 대상 데이터
| 데이터 | 중요도 | 백업 방법 | 비고 |
|--------|--------|-----------|------|
| PostgreSQL DB | **필수** | pg_dump SQL | 기사, 타임라인, 추적 요청, 검색 로그 |
| Qdrant 벡터 DB | **필수** | snapshot API | 기사 임베딩 벡터 (1024차원) |
| `.env` 파일 | **필수** | 직접 복사 | Azure API 키, DB 비밀번호 등 민감정보 |
| Redis | 불필요 | - | 캐시+Celery 브로커, 재시작 시 자동 재생성 |

---

## Phase 1: 기존 호스트에서 백업 생성

### 1-1. 백업 스크립트 실행

```bash
cd /home/zerolive/work/news-origin
bash migration/backup-for-migration.sh
```

이 스크립트가 생성하는 파일들:
```
migration/data/
  newsorigin_pg_migration_YYYYMMDD_HHMMSS.sql.gz    # PostgreSQL 전체 덤프
  newsorigin_qdrant_migration_YYYYMMDD_HHMMSS.snapshot  # Qdrant 벡터 스냅샷
  env_backup_YYYYMMDD_HHMMSS.env                     # .env 파일 사본
  migration_manifest.txt                              # 백업 파일 목록 + 체크섬
```

### 1-2. 백업 검증

```bash
# manifest 파일로 체크섬 확인
cd migration/data
sha256sum -c migration_manifest.txt
```

### 1-3. 기존 호스트 서비스 중지 (선택)

이전 완료 후 중복 크롤링 방지를 위해:
```bash
cd /home/zerolive/work/news-origin
docker compose -f docker-compose.prod.yml down
```

---

## Phase 2: 새 호스트 준비

### 2-1. 필수 소프트웨어 설치

```bash
# Docker + Docker Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 로그아웃 후 재로그인

# Git
sudo apt install -y git

# 기타 (선택)
sudo apt install -y curl make
```

### 2-2. 소스코드 클론

```bash
cd ~/work  # 또는 원하는 디렉토리
git clone <REPO_URL> news-origin
cd news-origin
```

### 2-3. 백업 파일 전송

기존 호스트의 `migration/data/` 폴더를 새 호스트로 전송:

```bash
# 기존 호스트에서 실행
scp -r migration/data/ NEW_USER@NEW_HOST:~/work/news-origin/migration/data/

# 또는 tar로 묶어서
cd migration && tar czf migration-data.tar.gz data/
scp migration-data.tar.gz NEW_USER@NEW_HOST:~/work/news-origin/migration/
# 새 호스트에서: cd migration && tar xzf migration-data.tar.gz
```

---

## Phase 3: 새 호스트에서 복원

### 3-1. .env 파일 복원

```bash
cd ~/work/news-origin

# 백업된 .env 파일에서 복원
cp migration/data/env_backup_*.env .env

# 필요시 수정 (새 호스트에 맞게)
# - CORS_ORIGINS: 새 도메인/IP로 변경
# - APP_SECRET_KEY: 보안을 위해 새로 생성 권장
# - PORT: 필요시 변경 (기본 10880)
```

### 3-2. .env에서 확인/수정할 항목

```bash
# 새 호스트 IP/도메인에 맞게 CORS 수정
CORS_ORIGINS=http://NEW_HOST:10880

# Azure API 키들은 그대로 유지 (클라우드 서비스이므로 호스트 무관)
# AZURE_OPENAI_EMBEDDING_ENDPOINT=...
# AZURE_OPENAI_EMBEDDING_API_KEY=...
# AZURE_OPENAI_ENDPOINT=...
# AZURE_OPENAI_API_KEY=...
```

### 3-3. 인프라 컨테이너 먼저 기동

```bash
cd ~/work/news-origin
docker compose -f docker-compose.prod.yml up -d postgres qdrant redis
# health check 통과까지 대기
sleep 15
docker compose -f docker-compose.prod.yml ps
# postgres, qdrant, redis 모두 healthy 확인
```

### 3-4. 복원 스크립트 실행

```bash
bash migration/restore-on-new-host.sh
```

이 스크립트가 수행하는 작업:
1. `migration/data/`에서 최신 백업 파일 자동 감지
2. PostgreSQL 복원 (pg_dump SQL 실행)
3. Qdrant 스냅샷 복원 (REST API)
4. 복원 결과 검증 (row count, collection info)

### 3-5. Alembic 마이그레이션 확인

```bash
# 백엔드 컨테이너에서 마이그레이션 상태 확인
docker compose -f docker-compose.prod.yml run --rm backend \
  alembic current

# 필요시 최신 마이그레이션 적용
docker compose -f docker-compose.prod.yml run --rm backend \
  alembic upgrade head
```

### 3-6. 전체 서비스 기동

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

> Docker 이미지 빌드에 20~30분 소요 (BERT NER + PyTorch 포함)

### 3-7. 기동 후 검증

```bash
# 헬스체크
curl http://localhost:10880/api/health

# 기사 수 확인
curl http://localhost:10880/api/trends/stats

# 트렌드 페이지 확인
curl -s http://localhost:10880/api/trends/hot | head -c 200

# 로그 확인
docker compose -f docker-compose.prod.yml logs -f --tail=50
```

---

## Phase 4: 검증 체크리스트

- [ ] `curl /api/health` → `{"status": "ok"}` 응답
- [ ] `curl /api/trends/stats` → 기사 수가 백업 전과 일치
- [ ] `curl /api/trends/hot` → 클러스터 데이터 정상 반환
- [ ] 브라우저에서 `http://NEW_HOST:10880` 접속 → 홈페이지 정상 로드
- [ ] 트렌드 페이지에서 클러스터 카드들이 표시됨
- [ ] 기사 추적 기능 테스트 (아무 기사 URL 입력 → 추적 시작)
- [ ] Flower 대시보드 `http://NEW_HOST:15555/flower/` → Celery 워커 online 확인
- [ ] 30분 대기 후 → Celery Beat에 의한 자동 크롤링이 동작하는지 확인
- [ ] `docker compose -f docker-compose.prod.yml logs celery-worker --tail=20` → 크롤링 로그 확인

---

## 트러블슈팅

### PostgreSQL 복원 실패
```bash
# 수동 복원
gunzip -k migration/data/newsorigin_pg_migration_*.sql.gz
docker exec -i newsorigin-postgres psql -U newsorigin -d newsorigin \
  < migration/data/newsorigin_pg_migration_*.sql
```

### Qdrant 복원 실패
```bash
# Qdrant 포트 확인 (프로덕션에서는 외부 포트 미노출)
# docker 내부 네트워크를 통해 복원해야 할 수 있음
docker exec newsorigin-qdrant curl -s http://localhost:6333/collections

# 스냅샷 수동 복원 - 컨테이너 내부에 파일 복사 후
docker cp migration/data/newsorigin_qdrant_migration_*.snapshot \
  newsorigin-qdrant:/qdrant/snapshots/
# Qdrant REST API로 복원
curl -X PUT "http://localhost:6333/collections/article_embeddings/snapshots/recover" \
  -H "Content-Type: application/json" \
  -d '{"location": "/qdrant/snapshots/SNAPSHOT_FILENAME"}'
```

### Celery 태스크가 실행되지 않음
```bash
# Redis 큐 확인 (CRITICAL: celery 큐를 사용해야 함)
docker exec newsorigin-redis redis-cli LLEN celery
docker exec newsorigin-redis redis-cli LLEN default
# default에 쌓이면 Beat 설정 문제 → celerybeat-schedule 파일 삭제 후 재시작

# Beat 재시작
docker compose -f docker-compose.prod.yml restart celery-beat
```

### 메모리 부족 (OOM)
```bash
# 컨테이너별 메모리 사용량 확인
docker stats --no-stream

# 가장 메모리를 많이 쓰는 것은 celery-worker (BERT NER ~740MB)
# mem_limit 조정이 필요하면 docker-compose.prod.yml 수정
```

### 포트 충돌
```bash
# 기본 포트: 10880 (nginx), 15555 (flower)
# 변경하려면 .env에서 PORT 설정
PORT=10880  # 원하는 포트로 변경
```

---

## 환경변수 참조 (.env)

새 호스트에서 반드시 설정해야 하는 환경변수:

| 변수 | 설명 | 비고 |
|------|------|------|
| `POSTGRES_USER` | DB 사용자명 | 기본값: newsorigin |
| `POSTGRES_PASSWORD` | DB 비밀번호 | 기본값: newsorigin |
| `POSTGRES_DB` | DB명 | 기본값: newsorigin |
| `APP_SECRET_KEY` | 앱 보안키 | 프로덕션에서 반드시 변경 |
| `AZURE_OPENAI_EMBEDDING_ENDPOINT` | 임베딩 API 엔드포인트 | Azure Portal에서 확인 |
| `AZURE_OPENAI_EMBEDDING_API_KEY` | 임베딩 API 키 | Azure Portal에서 확인 |
| `AZURE_OPENAI_ENDPOINT` | GPT API 엔드포인트 | 품질 평가용 |
| `AZURE_OPENAI_API_KEY` | GPT API 키 | 품질 평가용 |
| `CORS_ORIGINS` | 허용 오리진 | 새 호스트 도메인으로 변경 |
| `PORT` | Nginx 외부 포트 | 기본값: 10880 |

---

## 참고: Docker 볼륨 구조

```
# 프로덕션 Docker 볼륨 (docker-compose.prod.yml 기준)
news-origin_postgres_data   → PostgreSQL 데이터 파일
news-origin_qdrant_data     → Qdrant 벡터 스토리지
news-origin_redis_data      → Redis AOF/RDB (복원 불필요)
news-origin_frontend_dist   → 프론트엔드 빌드 산출물 (빌드 시 자동 생성)
```

## 참고: Alembic 마이그레이션 이력

```
001_initial_schema.py          # 초기 테이블 (Article, TrackingRequest, TimelineEntry, SearchLog)
002_add_error_message.py       # error_message 컬럼 추가
003_add_tracking_type.py       # tracking_type 컬럼 (instant/live)
004_add_metadata_category_index.py  # 메타데이터 인덱스
005_add_input_article_id.py    # input_article_id 컬럼
```

pg_dump로 전체 스키마+데이터를 복원하므로 Alembic을 처음부터 실행할 필요 없음.
`alembic current`로 현재 리비전만 확인하면 됨.
