#!/bin/bash
# restore-on-new-host.sh - 새 호스트에서 마이그레이션 데이터 복원
# backup-for-migration.sh로 생성한 백업 파일을 사용하여 복원합니다.
#
# 사전 조건:
#   1. git clone으로 소스코드 클론 완료
#   2. migration/data/ 폴더에 백업 파일 존재
#   3. .env 파일 설정 완료
#   4. postgres, qdrant, redis 컨테이너 실행 중 (healthy)
#
# 사용법:
#   cd ~/work/news-origin
#   bash migration/restore-on-new-host.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/migration/data"

# 환경변수 로드
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source <(grep -v '^#' "$PROJECT_DIR/.env" | grep -v '^\s*$')
    set +a
fi

DB_CONTAINER="newsorigin-postgres"
DB_NAME="${POSTGRES_DB:-newsorigin}"
DB_USER="${POSTGRES_USER:-newsorigin}"
DB_PASSWORD="${POSTGRES_PASSWORD:-newsorigin}"
QDRANT_CONTAINER="newsorigin-qdrant"

echo "============================================"
echo " News Origin - Migration Restore"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo ""

# ── 사전 확인 ──
echo "[CHECK] 백업 파일 확인..."
if [ ! -d "$BACKUP_DIR" ]; then
    echo "ERROR: migration/data/ 디렉토리가 없습니다."
    echo "  기존 호스트에서 backup-for-migration.sh를 먼저 실행하고,"
    echo "  migration/data/ 폴더를 이 호스트로 전송하세요."
    exit 1
fi

# 최신 백업 파일 찾기
PG_FILE=$(ls -t "$BACKUP_DIR"/newsorigin_pg_migration_*.sql.gz 2>/dev/null | head -1)
QDRANT_FILE=$(ls -t "$BACKUP_DIR"/newsorigin_qdrant_migration_*.snapshot 2>/dev/null | head -1)
MANIFEST_FILE="$BACKUP_DIR/migration_manifest.txt"

if [ -z "$PG_FILE" ]; then
    echo "ERROR: PostgreSQL 백업 파일을 찾을 수 없습니다."
    echo "  필요한 파일: migration/data/newsorigin_pg_migration_*.sql.gz"
    exit 1
fi

echo "  PostgreSQL: $(basename "$PG_FILE")"
if [ -n "$QDRANT_FILE" ]; then
    echo "  Qdrant:     $(basename "$QDRANT_FILE")"
else
    echo "  Qdrant:     (없음 - 건너뜀)"
fi
echo ""

# 체크섬 검증
if [ -f "$MANIFEST_FILE" ]; then
    echo "[CHECK] 체크섬 검증..."
    cd "$BACKUP_DIR"
    if sha256sum -c "$MANIFEST_FILE" --status 2>/dev/null; then
        echo "  체크섬 검증 통과"
    else
        echo "  WARNING: 체크섬 불일치! 파일이 손상되었을 수 있습니다."
        read -p "  계속 진행하시겠습니까? (y/N): " CONTINUE
        if [ "$CONTINUE" != "y" ] && [ "$CONTINUE" != "Y" ]; then
            exit 1
        fi
    fi
    cd "$PROJECT_DIR"
    echo ""
fi

# Docker 컨테이너 확인
echo "[CHECK] Docker 컨테이너 상태 확인..."
if ! docker ps --filter "name=$DB_CONTAINER" --filter "status=running" -q | grep -q .; then
    echo "ERROR: PostgreSQL 컨테이너가 실행 중이지 않습니다."
    echo "  먼저 인프라를 기동하세요:"
    echo "  docker compose -f docker-compose.prod.yml up -d postgres qdrant redis"
    echo "  sleep 15  # healthy 대기"
    exit 1
fi
echo "  PostgreSQL: running"

QDRANT_RUNNING=false
if docker ps --filter "name=$QDRANT_CONTAINER" --filter "status=running" -q | grep -q .; then
    echo "  Qdrant: running"
    QDRANT_RUNNING=true
else
    echo "  Qdrant: not running"
fi
echo ""

# ── 1. PostgreSQL 복원 ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[1/2] PostgreSQL 복원"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "  압축 해제 중..."
PG_SQL_FILE="${PG_FILE%.gz}"
if [ ! -f "$PG_SQL_FILE" ]; then
    gunzip -k "$PG_FILE"
fi

echo "  DB 복원 중... ($(du -h "$PG_SQL_FILE" | cut -f1))"
# --single-transaction으로 원자적 복원
docker exec -i -e PGPASSWORD="$DB_PASSWORD" "$DB_CONTAINER" \
    psql -U "$DB_USER" -d "$DB_NAME" --single-transaction -q \
    < "$PG_SQL_FILE" 2>&1 | tail -5

# 복원 검증
echo "  복원 검증..."
RESTORED_ARTICLES=$(docker exec -e PGPASSWORD="$DB_PASSWORD" "$DB_CONTAINER" \
    psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM articles;" 2>/dev/null | tr -d ' ')
RESTORED_TRACKING=$(docker exec -e PGPASSWORD="$DB_PASSWORD" "$DB_CONTAINER" \
    psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM tracking_requests;" 2>/dev/null | tr -d ' ')
RESTORED_TIMELINE=$(docker exec -e PGPASSWORD="$DB_PASSWORD" "$DB_CONTAINER" \
    psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM timeline_entries;" 2>/dev/null | tr -d ' ')

echo "  복원된 레코드:"
echo "    articles: $RESTORED_ARTICLES"
echo "    tracking_requests: $RESTORED_TRACKING"
echo "    timeline_entries: $RESTORED_TIMELINE"

# Alembic 버전 확인
ALEMBIC_VERSION=$(docker exec -e PGPASSWORD="$DB_PASSWORD" "$DB_CONTAINER" \
    psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT version_num FROM alembic_version;" 2>/dev/null | tr -d ' ')
echo "    alembic_version: ${ALEMBIC_VERSION:-없음}"

# 임시 SQL 파일 정리
rm -f "$PG_SQL_FILE"

echo "  PostgreSQL 복원 완료"
echo ""

# ── 2. Qdrant 복원 ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[2/2] Qdrant 벡터 DB 복원"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -z "$QDRANT_FILE" ]; then
    echo "  SKIP: Qdrant 백업 파일 없음"
    echo "  벡터 데이터 없이 서비스가 시작됩니다."
    echo "  기사 임베딩은 크롤링 시 자동으로 다시 생성됩니다."
elif [ "$QDRANT_RUNNING" = false ]; then
    echo "  SKIP: Qdrant 컨테이너 미실행"
else
    SNAPSHOT_BASENAME=$(basename "$QDRANT_FILE")
    QDRANT_SIZE=$(du -h "$QDRANT_FILE" | cut -f1)
    echo "  스냅샷 복원 중... ($QDRANT_SIZE)"

    # 스냅샷 파일을 컨테이너 내부로 복사
    docker cp "$QDRANT_FILE" "$QDRANT_CONTAINER:/tmp/$SNAPSHOT_BASENAME"

    # 기존 컬렉션이 있으면 삭제 (clean restore)
    docker exec "$QDRANT_CONTAINER" \
        curl -s -X DELETE "http://localhost:6333/collections/article_embeddings" > /dev/null 2>&1 || true
    sleep 2

    # 스냅샷으로 컬렉션 복원
    RESTORE_RESPONSE=$(docker exec "$QDRANT_CONTAINER" \
        curl -s -X PUT "http://localhost:6333/collections/article_embeddings/snapshots/recover" \
        -H "Content-Type: application/json" \
        -d "{\"location\": \"/tmp/$SNAPSHOT_BASENAME\"}" 2>/dev/null)

    echo "  복원 응답: $RESTORE_RESPONSE"

    # 복원 검증 (Qdrant가 스냅샷을 로딩하는 데 시간이 걸릴 수 있음)
    sleep 3
    RESTORED_VECTORS=$(docker exec "$QDRANT_CONTAINER" \
        curl -s "http://localhost:6333/collections/article_embeddings" 2>/dev/null \
        | grep -oP '"points_count"\s*:\s*\d+' | grep -oP '\d+' || echo "확인 실패")

    echo "  복원된 벡터 수: $RESTORED_VECTORS"

    # 임시 파일 정리
    docker exec "$QDRANT_CONTAINER" rm -f "/tmp/$SNAPSHOT_BASENAME"

    echo "  Qdrant 복원 완료"
fi
echo ""

# ── 결과 요약 ──
echo "============================================"
echo " 복원 완료!"
echo "============================================"
echo ""
echo " PostgreSQL:"
echo "   articles: $RESTORED_ARTICLES"
echo "   tracking_requests: $RESTORED_TRACKING"
echo "   timeline_entries: $RESTORED_TIMELINE"
echo "   alembic_version: ${ALEMBIC_VERSION:-없음}"
echo ""
if [ -n "$QDRANT_FILE" ] && [ "$QDRANT_RUNNING" = true ]; then
    echo " Qdrant:"
    echo "   vectors: ${RESTORED_VECTORS:-확인 실패}"
    echo ""
fi
echo " 다음 단계:"
echo "   1. 전체 서비스 기동:"
echo "      docker compose -f docker-compose.prod.yml up -d --build"
echo "      (빌드에 20~30분 소요)"
echo ""
echo "   2. 헬스체크:"
echo "      curl http://localhost:10880/api/health"
echo ""
echo "   3. 브라우저에서 확인:"
echo "      http://localhost:10880"
echo ""
