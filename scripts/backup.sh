#!/bin/bash
# backup.sh - News Origin 자동 백업 스크립트
# PostgreSQL pg_dump + Qdrant snapshot 생성 + 7일 이전 백업 삭제
#
# Cron 설정 예시 (매일 오전 3시):
# 0 3 * * * /home/zerolive/work/news-origin/scripts/backup.sh >> /home/zerolive/work/news-origin/backups/backup.log 2>&1
#
# 환경변수 설정 (cron에서 실행 시 필요):
# export POSTGRES_PASSWORD=your_password
# 또는 .pgpass 파일 사용 (~/.pgpass: hostname:port:database:username:password)

set -euo pipefail

# 설정
BACKUP_DIR="/home/zerolive/work/news-origin/backups"
PROJECT_DIR="/home/zerolive/work/news-origin"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

# 환경변수 로드 (.env 파일이 있으면)
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
fi

# DB 연결정보 (docker-compose.prod.yml 기본값)
DB_CONTAINER="newsorigin-postgres"
DB_NAME="${POSTGRES_DB:-newsorigin}"
DB_USER="${POSTGRES_USER:-newsorigin}"
DB_PASSWORD="${POSTGRES_PASSWORD:-newsorigin}"
QDRANT_HOST="http://localhost:6333"

# 백업 디렉토리 생성
mkdir -p "$BACKUP_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ===== 백업 시작 ====="

# 1. PostgreSQL 백업
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PostgreSQL 백업 중..."
PG_BACKUP_FILE="$BACKUP_DIR/newsorigin_pg_$TIMESTAMP.sql"

if docker ps --filter "name=$DB_CONTAINER" --filter "status=running" -q | grep -q .; then
    docker exec -e PGPASSWORD="$DB_PASSWORD" "$DB_CONTAINER" \
        pg_dump -U "$DB_USER" -d "$DB_NAME" \
        --no-owner --no-acl --clean --if-exists \
        > "$PG_BACKUP_FILE"

    # 압축
    gzip "$PG_BACKUP_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] PostgreSQL 백업 완료: ${PG_BACKUP_FILE}.gz"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: PostgreSQL 컨테이너가 실행 중이지 않음"
    exit 1
fi

# 2. Qdrant 백업
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Qdrant 백업 중..."
QDRANT_BACKUP_FILE="$BACKUP_DIR/newsorigin_qdrant_$TIMESTAMP.snapshot"

# Qdrant snapshot 생성 요청
SNAPSHOT_RESPONSE=$(curl -s -X POST "$QDRANT_HOST/collections/article_embeddings/snapshots" \
    -H "Content-Type: application/json")

# snapshot 파일명 추출
SNAPSHOT_NAME=$(echo "$SNAPSHOT_RESPONSE" | grep -o '"name":"[^"]*"' | cut -d'"' -f4)

if [ -n "$SNAPSHOT_NAME" ]; then
    # 잠시 대기 (snapshot 생성 완료)
    sleep 2

    # snapshot 다운로드
    curl -s "$QDRANT_HOST/collections/article_embeddings/snapshots/$SNAPSHOT_NAME" \
        -o "$QDRANT_BACKUP_FILE"

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Qdrant 백업 완료: $QDRANT_BACKUP_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: Qdrant snapshot 생성 실패 (응답: $SNAPSHOT_RESPONSE)"
fi

# 3. 오래된 백업 삭제 (7일 초과)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 오래된 백업 정리 중 ($RETENTION_DAYS일 초과)..."
DELETED_COUNT=0

# PostgreSQL 백업 삭제
while IFS= read -r old_file; do
    rm -f "$old_file"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 삭제: $old_file"
    ((DELETED_COUNT++))
done < <(find "$BACKUP_DIR" -name "newsorigin_pg_*.sql.gz" -type f -mtime +$RETENTION_DAYS)

# Qdrant 백업 삭제
while IFS= read -r old_file; do
    rm -f "$old_file"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 삭제: $old_file"
    ((DELETED_COUNT++))
done < <(find "$BACKUP_DIR" -name "newsorigin_qdrant_*.snapshot" -type f -mtime +$RETENTION_DAYS)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 정리 완료: ${DELETED_COUNT}개 파일 삭제"

# 4. 백업 통계
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ===== 백업 완료 ====="
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 현재 백업 파일 수:"
echo "  PostgreSQL: $(find "$BACKUP_DIR" -name "newsorigin_pg_*.sql.gz" -type f | wc -l)개"
echo "  Qdrant: $(find "$BACKUP_DIR" -name "newsorigin_qdrant_*.snapshot" -type f | wc -l)개"
echo "  총 용량: $(du -sh "$BACKUP_DIR" | cut -f1)"
