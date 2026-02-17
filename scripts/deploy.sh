#!/bin/bash
# deploy.sh - 경량 배포 스크립트
# Docker 이미지 재빌드 없이 변경사항 배포
#
# 사용법:
#   ./scripts/deploy.sh frontend    # 프론트엔드만 배포
#   ./scripts/deploy.sh backend     # 백엔드만 재시작
#   ./scripts/deploy.sh all         # 전체 배포
#   ./scripts/deploy.sh full        # Docker 이미지 재빌드 포함 전체 배포

set -e
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.prod.yml"

deploy_frontend() {
    echo "=== Frontend 배포 ==="
    echo "[1/4] 로컬 빌드..."
    cd frontend && npm run build && cd ..

    echo "[2/4] 기존 컨테이너 정지..."
    $COMPOSE stop frontend nginx

    echo "[3/4] 볼륨에 빌드 결과 복사..."
    # 임시 컨테이너로 볼륨에 복사
    docker run --rm \
        -v news-origin_frontend_dist:/dest \
        -v "$(pwd)/frontend/dist:/src:ro" \
        alpine sh -c "rm -rf /dest/* && cp -r /src/* /dest/"

    echo "[4/4] 컨테이너 재시작..."
    $COMPOSE start frontend nginx

    echo "✓ Frontend 배포 완료"
}

deploy_backend() {
    echo "=== Backend 배포 ==="
    echo "[1/2] 컨테이너 재시작..."
    $COMPOSE up -d --build --force-recreate backend celery-worker celery-beat

    echo "[2/2] 헬스체크 대기..."
    sleep 5
    if curl -sf http://localhost:10880/api/health > /dev/null; then
        echo "✓ Backend 배포 완료 (healthy)"
    else
        echo "⚠ Backend 시작됨 - 헬스체크 확인 필요"
    fi
}

deploy_full() {
    echo "=== Full 배포 (이미지 재빌드) ==="
    $COMPOSE down
    docker volume rm news-origin_frontend_dist 2>/dev/null || true
    $COMPOSE up -d --build
    echo "✓ Full 배포 완료"
}

case "${1:-all}" in
    frontend|fe)
        deploy_frontend
        ;;
    backend|be)
        deploy_backend
        ;;
    all)
        deploy_frontend
        deploy_backend
        ;;
    full)
        deploy_full
        ;;
    *)
        echo "사용법: $0 {frontend|backend|all|full}"
        echo ""
        echo "  frontend (fe)  - 프론트엔드만 배포 (로컬 빌드 → 볼륨 복사, ~30초)"
        echo "  backend  (be)  - 백엔드만 재빌드+재시작 (~3-5분)"
        echo "  all            - 프론트+백엔드 (기본값)"
        echo "  full           - Docker 이미지 전체 재빌드 (~20-30분)"
        exit 1
        ;;
esac
