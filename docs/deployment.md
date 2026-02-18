# Deployment Guide

## 경량 배포 (deploy.sh)

프로덕션 배포는 `scripts/deploy.sh`를 사용합니다. Docker 이미지 재빌드 없이 빠르게 변경사항을 반영합니다.

```bash
./scripts/deploy.sh frontend    # 프론트엔드만 (~30초, 로컬 빌드 → 볼륨 복사)
./scripts/deploy.sh backend     # 백엔드만 (~3-5분, 이미지 재빌드 + 재시작)
./scripts/deploy.sh all         # 프론트+백엔드 (기본값)
./scripts/deploy.sh full        # Docker 이미지 전체 재빌드 (~20-30분)
```

### Frontend 배포 흐름
1. `frontend/` 에서 `npm run build` (로컬)
2. 기존 frontend/nginx 컨테이너 정지
3. 빌드 결과를 Docker 볼륨(`frontend_dist`)에 복사
4. 컨테이너 재시작

### Backend 배포 흐름
1. `docker compose up -d --build --force-recreate backend celery-worker celery-beat`
2. 헬스체크 (`/api/health`)

## Docker Compose 프로덕션 빌드 (수동)

이미지 재빌드가 필요할 때:

```bash
docker compose -f docker-compose.prod.yml up -d --build          # 전체
docker compose -f docker-compose.prod.yml up -d --build backend   # 백엔드만
docker compose -f docker-compose.prod.yml up -d --build frontend  # 프론트엔드만
```

## 주의사항

- **빌드 시간**: CUDA/PyTorch 포함으로 backend 이미지 빌드에 20~30분 소요
- **Celery Beat**: 재시작 시 `/tmp/celerybeat-schedule.*` 잔여 파일이 있으면 스케줄 불일치 발생 (docker-compose.prod.yml에서 자동 삭제 설정됨)
- **메모리**: celery-worker 1024MB 한도, backend 384MB 한도 (호스트 3.8GB RAM)
- **deploy.sh 사용 권장**: `full` 모드 대신 `frontend`/`backend` 분리 배포로 시간 절약
