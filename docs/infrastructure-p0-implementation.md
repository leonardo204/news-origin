# Infrastructure P0 구현 완료

구현 날짜: 2026-02-16
작업자: Executor Agent

## 작업 요약

News Origin 프로젝트의 Infrastructure P0 항목 3개를 구현하였습니다.

## 1. DB 자동 백업 스크립트 ✓

### 생성 파일
- `/home/zerolive/work/news-origin/scripts/backup.sh` (실행 권한: 755)

### 기능
- **PostgreSQL 백업**: `pg_dump`로 SQL 덤프 생성 후 gzip 압축
- **Qdrant 백업**: snapshot API로 벡터 DB 백업
- **자동 정리**: 7일 초과 백업 파일 자동 삭제
- **백업 위치**: `/home/zerolive/work/news-origin/backups/`
- **환경변수 지원**: `.env` 파일 자동 로드

### Cron 설정 예시
```bash
# 매일 오전 3시 실행
0 3 * * * /home/zerolive/work/news-origin/scripts/backup.sh >> /home/zerolive/work/news-origin/backups/backup.log 2>&1
```

### 수동 실행
```bash
cd /home/zerolive/work/news-origin
./scripts/backup.sh
```

### 복구 방법
```bash
# PostgreSQL 복구
gunzip backups/newsorigin_pg_YYYYMMDD_HHMMSS.sql.gz
docker exec -i newsorigin-postgres psql -U newsorigin -d newsorigin < backups/newsorigin_pg_YYYYMMDD_HHMMSS.sql

# Qdrant 복구 (Qdrant 문서 참조)
curl -X PUT "http://localhost:6333/collections/article_embeddings/snapshots/upload" \
  --data-binary @backups/newsorigin_qdrant_YYYYMMDD_HHMMSS.snapshot
```

## 2. Celery 태스크 모니터링 (Flower) ✓

### 변경 파일
- `docker-compose.prod.yml`: flower 서비스 추가
- `docker/nginx/nginx.prod.conf`: `/flower/` 프록시 설정 추가

### Flower 서비스 설정
```yaml
flower:
  image: mher/flower:2.0
  container_name: newsorigin-flower
  command: celery --broker=redis://redis:6379/1 flower --port=5555 --url_prefix=flower
  ports:
    - "15555:5555"
  depends_on:
    - redis
  mem_limit: 128m
  restart: unless-stopped
```

### 접근 방법
- **직접 접근**: `http://localhost:15555` (외부 포트)
- **Nginx 프록시**: `http://localhost:10880/flower/` (프로덕션)

### 모니터링 기능
- 실시간 태스크 실행 현황
- 워커 상태 및 성능 메트릭
- 태스크 히스토리 및 실패 로그
- Redis 브로커 통계

## 3. Rate Limiting 적용 ✓

### 변경 파일
- `docker/nginx/nginx.prod.conf`

### Rate Limit Zone 정의
```nginx
limit_req_zone $binary_remote_addr zone=api_search:10m rate=10r/m;   # 크롤링 요청 (분당 10회)
limit_req_zone $binary_remote_addr zone=api_trends:10m rate=30r/m;   # 트렌드 API (분당 30회)
limit_req_zone $binary_remote_addr zone=api_general:10m rate=60r/m;  # 일반 API (분당 60회)
limit_req_status 429;  # rate limit 초과 시 429 응답
```

### 적용 대상
1. **api_search (10r/m, burst=5)**
   - `/api/articles/track`
   - `/api/articles/confirm`
   - `/api/articles/live-track`

2. **api_trends (30r/m, burst=10)**
   - `/api/trends/hot`
   - `/api/trends/stats`
   - `/api/trends/article-trends`
   - `/api/trends/recent-articles`

3. **api_general (60r/m, burst=20)**
   - 기타 `/api/*` 엔드포인트

### Rate Limit 예외
- SSE 엔드포인트: `/api/trends/events` (제한 없음)
- 정적 파일: `/assets/`, `/` (제한 없음)
- API 문서: `/docs`, `/redoc`, `/openapi.json` (제한 없음)

## 배포 방법

### 1. 백업 스크립트 테스트
```bash
cd /home/zerolive/work/news-origin
./scripts/backup.sh
ls -lh backups/
```

### 2. Docker Compose 재시작 (Flower 추가)
```bash
cd /home/zerolive/work/news-origin
docker compose -f docker-compose.prod.yml up -d --build flower
docker compose -f docker-compose.prod.yml restart nginx
```

### 3. Flower 접속 확인
```bash
curl -I http://localhost:15555
# 또는
curl -I http://localhost:10880/flower/
```

### 4. Rate Limiting 테스트
```bash
# 연속 요청으로 429 응답 확인
for i in {1..15}; do
  curl -w "%{http_code}\n" http://localhost:10880/api/articles/track -X POST -d "{}" -H "Content-Type: application/json"
done
# 11번째 요청부터 429 응답 예상
```

## 메모리 영향 분석

### Flower 서비스 추가
- **메모리 할당**: 128MB (mem_limit)
- **예상 실사용**: ~50MB
- **전체 메모리**: 기존 2.5GB → 2.6GB (호스트 3.8GB의 68%)

### Rate Limiting
- **Nginx zone 메모리**: 30MB (api_search:10m + api_trends:10m + api_general:10m)
- **영향**: 미미 (zone은 IP 주소 추적용 공유 메모리)

## 주의사항

1. **백업 스크립트**
   - cron 실행 시 환경변수 경로 확인 필요
   - `/home/zerolive/work/news-origin/backups/` 디스크 공간 모니터링
   - 복구 테스트 정기 실시 권장

2. **Flower**
   - 외부 접근 시 인증 설정 권장 (현재 미적용)
   - `--basic_auth=user:password` 옵션 추가 고려

3. **Rate Limiting**
   - 사용자 극소수 환경 고려하여 관대하게 설정
   - 필요 시 zone rate 조정 가능 (nginx.prod.conf 수정 후 reload)

## 검증 체크리스트

- [x] backup.sh 실행 권한 설정 (755)
- [x] docker-compose.prod.yml에 flower 서비스 추가
- [x] nginx.prod.conf에 rate limit zone 정의
- [x] nginx.prod.conf에 /flower/ 프록시 설정
- [x] 각 API 엔드포인트에 적절한 rate limit 적용
- [x] limit_req_status 429 설정
- [x] 기존 설정 보존 (캐싱, SSE, 정적 파일)

## 참고 문서

- Flower 문서: https://flower.readthedocs.io/
- Nginx rate limiting: https://nginx.org/en/docs/http/ngx_http_limit_req_module.html
- PostgreSQL pg_dump: https://www.postgresql.org/docs/current/app-pgdump.html
- Qdrant snapshot API: https://qdrant.tech/documentation/concepts/snapshots/
