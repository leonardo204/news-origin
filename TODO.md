# News Origin - 서비스 개선 TODO

> **작성일**: 2026-02-18
> **현재 버전**: v1.3.0 (Production)
> **최종 업데이트**: 2026-02-18 (19개 항목 완료)

---

## 우선순위

| 등급 | 의미 | 기준 |
|------|------|------|
| **P0** | 즉시 | 안정성/보안/성능에 직접 영향 |
| **P1** | 높음 | 사용자 경험 및 운영 효율성 |
| **P2** | 중간 | 유지보수성/확장성 향상 |
| **P3** | 낮음 | 향후 확장/편의성 |

---

## 미완료 항목 (11개)

### P1

- [ ] **크롤링 통계 대시보드 API**
  - 현재: 크롤링 성공/실패/스킵 수를 로그로만 확인
  - 개선: `/api/admin/crawl-stats` 엔드포인트 추가
  - 일별 크롤링 건수, 임베딩 성공률, 카테고리별 분포 반환

- [ ] **클러스터링 품질 메트릭**
  - 현재: 클러스터링 결과의 품질을 정량적으로 측정하지 않음
  - 개선: 실루엣 스코어, 클러스터 내/간 평균 유사도 로깅
  - GPT-5 샘플링 평가와 연계하여 품질 추이 추적

- [ ] **사용자 인증 (기본)**
  - 현재: 인증 없이 모든 기능 오픈
  - 개선: 관리자 대시보드 접근 제한 (기본 인증 또는 세션)
  - Flower 대시보드(/flower/)도 인증 필요

### P2

- [ ] **개발 환경 Docker 분리**
  - 현재: 프로덕션과 Dockerfile 공유
  - 개선: 개발용 경량 Dockerfile (BERT/PyTorch 제외, mock 임베딩)
  - 빌드 시간 20-30분 → 5분 이내 목표

- [ ] **RSS 피드 커스텀 설정**
  - 현재: 하드코딩된 카테고리 피드 + 고정 언론사 목록
  - 개선: 관리자 UI에서 피드 URL 추가/수정/삭제
  - 피드별 수집 상태 모니터링

- [ ] **React 19 마이그레이션**
  - 현재: React 18.3 (CLAUDE.md에는 React 19로 기재)
  - `@xyflow/react`가 React 19 호환 확인됨
  - 점진적 마이그레이션 (use hook, Server Components는 해당 없음)

- [ ] **Pydantic → TypeScript 타입 자동 생성**
  - 현재: Zod 스키마로 런타임 검증 구현됨
  - 개선: 백엔드 Pydantic 스키마에서 TypeScript 타입 자동 생성
  - `pydantic-to-typescript` 또는 OpenAPI 기반 코드젠

### P3

- [ ] **API 공개 & 문서화**
  - FastAPI auto-docs 정리, API 사용 가이드 작성
  - Rate limit/인증 안내 포함

- [ ] **멀티 언어 뉴스 지원**
  - 영어/일본어 Google News RSS 추가
  - 크로스 언어 기사 유사도 비교 (현재 임베딩 모델이 multilingual 지원)

- [ ] **i18n 다국어 지원**
  - 현재: 한국어 하드코딩
  - `react-i18next` 도입, 영어 지원 추가
  - 우선순위 낮음 (사용자 전원 한국어)

---

## 완료 항목 (26개)

| 날짜 | 항목 | 비고 |
|------|------|------|
| 2026-02-18 | 전파트리 React Flow 마이그레이션 | @antv/g6 → @xyflow/react, 번들 83% 감소 |
| 2026-02-18 | 전파트리 카드형 노드 디자인 | 흰색 배경 + 좌측 컬러바 + 그림자 |
| 2026-02-18 | 전파트리 모달 풀사이즈 | 95vh × 97vw |
| 2026-02-18 | 트렌드 캐시 워밍 | 크롤링 후 24h/7d/30d 자동 계산 → Redis TTL 1시간 |
| 2026-02-18 | nginx/axios 타임아웃 조정 | proxy_read_timeout 180s, axios 120s |
| 2026-02-18 | Celery stale Redis lock 수정 | `_reset_redis()` + `lock_acquired` 가드 |
| 2026-02-18 | 임베딩 실패 기사 DB 미저장 정책 | 벡터 검색 불가 기사 사전 차단 |
| 2026-02-18 | 임베딩 실패 재시도 큐 | Redis queue + 15분 Beat, 최대 3회 재시도 |
| 2026-02-18 | Celery Worker 메모리 모니터링 | psutil RSS 체크 + Discord 웹훅 알림 |
| 2026-02-18 | API 페이지네이션 | `/recent-articles` offset/limit + total |
| 2026-02-18 | 1회성 마이그레이션 태스크 정리 | tasks.py ~170줄 제거 |
| 2026-02-18 | 캐시 워밍 폴백 강화 | 빈 결과 반환으로 타임아웃 방지 |
| 2026-02-18 | get_article_text() 정리 | content 파라미터 제거 + 테스트 재작성 |
| 2026-02-18 | ECharts 번들 최적화 | echarts/core 모듈별 import |
| 2026-02-18 | 전파트리 대량 노드 성능 | MiniMap + Controls 추가 |
| 2026-02-18 | 오프라인/네트워크 에러 UX | 오프라인 배너 + 자동 재연결 |
| 2026-02-18 | URL 기반 상태 공유 | TrendsPage period URL 연동 |
| 2026-02-18 | PWA 지원 | manifest + service worker + offline.html |
| 2026-02-18 | Web Vitals 모니터링 | CLS/LCP/FCP/TTFB/INP 측정 |
| 2026-02-18 | 리소스 사용량 알림 | scripts/monitor.sh + Discord webhook |
| 2026-02-18 | Docker 이미지 최적화 | Dockerfile.prod COPY 경로 수정 |
| 2026-02-18 | 임베딩 품질 모니터링 | /api/health/embeddings 엔드포인트 |
| 2026-02-18 | 로그 로테이션 | docker-compose logging options |
| 2026-02-18 | 알림/웹훅 시스템 | Discord webhook.py + 4개 알림 포인트 |
| 2026-02-18 | 기사 비교 뷰 | Trends + Timeline 비교 모달 |
| 2026-02-18 | 테스트 커버리지 확대 | category 23 + webhook 5 + embedding 8 tests |

---

## 상세 참고

기존 고도화 분석 문서: [`docs/todo-enhancement.md`](docs/todo-enhancement.md) (32/42 항목 완료)
