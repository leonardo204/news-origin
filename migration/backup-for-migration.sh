#!/bin/bash
# backup-for-migration.sh - 호스트 마이그레이션용 전체 백업 스크립트
# 기존 호스트에서 실행하여 새 호스트로 이전할 데이터를 백업합니다.
#
# 사용법:
#   cd /home/zerolive/work/news-origin
#   bash migration/backup-for-migration.sh
#
# 생성 파일:
#   migration/data/newsorigin_pg_migration_TIMESTAMP.sql.gz
#   migration/data/newsorigin_qdrant_migration_TIMESTAMP.snapshot
#   migration/data/env_backup_TIMESTAMP.env
#   migration/data/migration_manifest.txt

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/migration/data"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

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
echo " News Origin - Migration Backup"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo ""

# 백업 디렉토리 생성
mkdir -p "$BACKUP_DIR"

# ── 사전 확인 ──
echo "[CHECK] Docker 컨테이너 상태 확인..."
RUNNING_CONTAINERS=$(docker ps --filter "name=newsorigin" --format "{{.Names}}" 2>/dev/null || true)

if ! echo "$RUNNING_CONTAINERS" | grep -q "$DB_CONTAINER"; then
    echo "ERROR: PostgreSQL 컨테이너($DB_CONTAINER)가 실행 중이지 않습니다."
    echo "  docker compose -f docker-compose.prod.yml up -d postgres"
    exit 1
fi

if ! echo "$RUNNING_CONTAINERS" | grep -q "$QDRANT_CONTAINER"; then
    echo "WARNING: Qdrant 컨테이너($QDRANT_CONTAINER)가 실행 중이지 않습니다."
    echo "  Qdrant 백업을 건너뜁니다."
    SKIP_QDRANT=true
else
    SKIP_QDRANT=false
fi

echo "  실행 중: $(echo "$RUNNING_CONTAINERS" | tr '\n' ', ')"
echo ""

VECTOR_COUNT="unknown"

# ── 1. PostgreSQL 백업 ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[1/4] PostgreSQL 백업"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

PG_DUMP_FILE="$BACKUP_DIR/newsorigin_pg_migration_$TIMESTAMP.sql"
PG_GZ_FILE="${PG_DUMP_FILE}.gz"

echo "  덤프 중... ($DB_NAME)"
docker exec -e PGPASSWORD="$DB_PASSWORD" "$DB_CONTAINER" \
    pg_dump -U "$DB_USER" -d "$DB_NAME" \
    --no-owner --no-acl --clean --if-exists \
    > "$PG_DUMP_FILE"

# 기사 수 기록 (검증용)
ARTICLE_COUNT=$(docker exec -e PGPASSWORD="$DB_PASSWORD" "$DB_CONTAINER" \
    psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM articles;" 2>/dev/null | tr -d ' ')
TRACKING_COUNT=$(docker exec -e PGPASSWORD="$DB_PASSWORD" "$DB_CONTAINER" \
    psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM tracking_requests;" 2>/dev/null | tr -d ' ')
TIMELINE_COUNT=$(docker exec -e PGPASSWORD="$DB_PASSWORD" "$DB_CONTAINER" \
    psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM timeline_entries;" 2>/dev/null | tr -d ' ')

echo "  압축 중..."
gzip "$PG_DUMP_FILE"

PG_SIZE=$(du -h "$PG_GZ_FILE" | cut -f1)
echo "  완료: $(basename "$PG_GZ_FILE") ($PG_SIZE)"
echo "  DB 레코드 수:"
echo "    articles: $ARTICLE_COUNT"
echo "    tracking_requests: $TRACKING_COUNT"
echo "    timeline_entries: $TIMELINE_COUNT"
echo ""

# ── 2. Qdrant 벡터 DB 백업 ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[2/4] Qdrant 벡터 DB 백업"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

QDRANT_FILE="$BACKUP_DIR/newsorigin_qdrant_migration_$TIMESTAMP.snapshot"

if [ "$SKIP_QDRANT" = true ]; then
    echo "  SKIP: Qdrant 컨테이너 미실행"
else
    # Qdrant 컨테이너에 curl이 없으므로 컨테이너 IP를 통해 호스트에서 직접 접근
    QDRANT_IP=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$QDRANT_CONTAINER")
    QDRANT_URL="http://$QDRANT_IP:6333"

    echo "  Qdrant 접근: $QDRANT_URL"
    echo "  스냅샷 생성 요청 중..."

    SNAPSHOT_RESPONSE=$(curl -s -X POST "$QDRANT_URL/collections/article_embeddings/snapshots" \
        -H "Content-Type: application/json" 2>/dev/null)

    SNAPSHOT_NAME=$(echo "$SNAPSHOT_RESPONSE" | grep -oP '"name"\s*:\s*"[^"]*"' | head -1 | cut -d'"' -f4)

    if [ -n "$SNAPSHOT_NAME" ]; then
        echo "  스냅샷 생성됨: $SNAPSHOT_NAME"
        sleep 3

        # 호스트에서 직접 다운로드
        curl -s "$QDRANT_URL/collections/article_embeddings/snapshots/$SNAPSHOT_NAME" \
            -o "$QDRANT_FILE" 2>/dev/null

        # 벡터 수 확인
        VECTOR_COUNT=$(curl -s "$QDRANT_URL/collections/article_embeddings" 2>/dev/null \
            | grep -oP '"points_count"\s*:\s*\d+' | grep -oP '\d+' || echo "unknown")

        QDRANT_SIZE=$(du -h "$QDRANT_FILE" | cut -f1)
        echo "  완료: $(basename "$QDRANT_FILE") ($QDRANT_SIZE)"
        echo "  벡터 수: $VECTOR_COUNT"
    else
        echo "  WARNING: Qdrant 스냅샷 생성 실패"
        echo "  응답: $SNAPSHOT_RESPONSE"
    fi
fi
echo ""

# ── 3. 민감 파일 백업 (.env 등) ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[3/4] 민감 파일 백업"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

SECRETS_DIR="$BACKUP_DIR/secrets_$TIMESTAMP"
mkdir -p "$SECRETS_DIR"

COPIED=0

# .env (API 키, DB 비밀번호)
if [ -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env" "$SECRETS_DIR/dot-env"
    echo "  .env → secrets/dot-env"
    COPIED=$((COPIED + 1))
fi

# .env.local (있으면)
if [ -f "$PROJECT_DIR/.env.local" ]; then
    cp "$PROJECT_DIR/.env.local" "$SECRETS_DIR/dot-env-local"
    echo "  .env.local → secrets/dot-env-local"
    COPIED=$((COPIED + 1))
fi

# Docker 설정 파일 (git에 있지만 새 호스트에서 클론 전 필요할 수 있음)
if [ -f "$PROJECT_DIR/docker/qdrant/config.yaml" ]; then
    cp "$PROJECT_DIR/docker/qdrant/config.yaml" "$SECRETS_DIR/qdrant-config.yaml"
    echo "  docker/qdrant/config.yaml → secrets/qdrant-config.yaml"
    COPIED=$((COPIED + 1))
fi

if [ -f "$PROJECT_DIR/docker/redis/redis.conf" ]; then
    cp "$PROJECT_DIR/docker/redis/redis.conf" "$SECRETS_DIR/redis.conf"
    echo "  docker/redis/redis.conf → secrets/redis.conf"
    COPIED=$((COPIED + 1))
fi

if [ -f "$PROJECT_DIR/docker/nginx/nginx.prod.conf" ]; then
    cp "$PROJECT_DIR/docker/nginx/nginx.prod.conf" "$SECRETS_DIR/nginx.prod.conf"
    echo "  docker/nginx/nginx.prod.conf → secrets/nginx.prod.conf"
    COPIED=$((COPIED + 1))
fi

# tar로 묶기
SECRETS_TAR="$BACKUP_DIR/secrets_$TIMESTAMP.tar.gz"
tar czf "$SECRETS_TAR" -C "$BACKUP_DIR" "secrets_$TIMESTAMP"
rm -rf "$SECRETS_DIR"

SECRETS_SIZE=$(du -h "$SECRETS_TAR" | cut -f1)
echo "  완료: $(basename "$SECRETS_TAR") ($SECRETS_SIZE, ${COPIED}개 파일)"
echo ""

# ── 4. Manifest 생성 (체크섬) ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[4/4] Manifest 생성 (SHA256 체크섬)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

MANIFEST_FILE="$BACKUP_DIR/migration_manifest.txt"

{
    echo "# News Origin Migration Backup Manifest"
    echo "# Generated: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "# Source Host: $(hostname)"
    echo "#"
    echo "# DB Records at backup time:"
    echo "#   articles: $ARTICLE_COUNT"
    echo "#   tracking_requests: $TRACKING_COUNT"
    echo "#   timeline_entries: $TIMELINE_COUNT"
    echo "#   qdrant vectors: $VECTOR_COUNT"
    echo "#"
    echo "# Verify with: cd migration/data && sha256sum -c migration_manifest.txt"
    echo ""
} > "$MANIFEST_FILE"

# 체크섬 추가
cd "$BACKUP_DIR"
for f in *"$TIMESTAMP"*; do
    if [ -f "$f" ]; then
        sha256sum "$f" >> "$MANIFEST_FILE"
    fi
done
cd "$PROJECT_DIR"

cat "$MANIFEST_FILE"
echo ""

# ── 결과 요약 ──
echo "============================================"
echo " 백업 완료!"
echo "============================================"
echo ""
echo " 백업 파일:"
ls -lh "$BACKUP_DIR"/*"$TIMESTAMP"* "$MANIFEST_FILE" 2>/dev/null
echo ""
echo " 총 백업 크기: $(du -sh "$BACKUP_DIR" | cut -f1)"
echo ""
echo " 다음 단계:"
echo "   1. migration/data/ 폴더를 새 호스트로 전송"
echo "      scp -r migration/data/ USER@NEW_HOST:~/work/news-origin/migration/data/"
echo ""
echo "   2. 새 호스트에서 소스코드 클론 + .env 복원"
echo "      git clone <REPO_URL> news-origin && cd news-origin"
echo "      tar xzf migration/data/secrets_*.tar.gz -C migration/data/"
echo "      cp migration/data/secrets_*/dot-env .env"
echo ""
echo "   3. 새 호스트에서 복원 스크립트 실행"
echo "      bash migration/restore-on-new-host.sh"
echo ""
