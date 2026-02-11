# News Origin - Implementation Plan

> Version: 0.2.0
> Date: 2025-02-11
> Status: Draft (v2 - 시각화/Vector DB/완성도 전면 개선)

---

## Changelog

| 버전 | 날짜 | 변경 사항 |
|------|------|-----------|
| 0.2.0 | 2025-02-11 | React Flow → AntV G6 + Apache ECharts 변경, pgvector → Qdrant 변경, PoC 제한 제거 |
| 0.1.0 | 2025-02-11 | 초안 작성 |

---

## 1. Executive Summary

**News Origin**은 특정 뉴스 기사의 최초 출처를 추적하고, 시간 흐름에 따른 전파 경로를 시각적으로 보여주는 웹 서비스입니다.

### 핵심 가치
- **Origin Tracking**: 뉴스의 최초 작성자/언론사/시점 확인
- **Propagation Flow**: 기사가 어떤 경로로 퍼져나갔는지 시각화
- **Explosion Detection**: 다수 언론사가 동시 보도하는 "폭발 시점" 감지
- **Lifecycle Visibility**: 기사의 생성(Origin) → 확산(Spread) → 소멸(Fade-out) 전 과정 가시화

---

## 2. Competitive Analysis (경쟁/유사 서비스 분석)

### 2.1 직접 경쟁 서비스 (없음 - 기회 영역)
현재 **뉴스 기사의 최초 출처 + 전파 타임라인**을 결합한 서비스는 존재하지 않음.

### 2.2 유사 서비스

| 서비스 | 유형 | 핵심 기능 | 차이점 |
|--------|------|-----------|--------|
| **NewsWhip** | 상용 (Enterprise) | 미디어 타임라인 분석, 스토리 전파 추적 | 엔터프라이즈 가격, API 비공개 |
| **Meltwater** | 상용 (Enterprise) | 270,000+ 소스 모니터링, 감성 분석 | 기업용, 출처 추적보다 모니터링 중심 |
| **Hoaxy** | 학술/무료 | 소셜미디어 기사 확산 시각화, 봇 탐지 | 소셜미디어 한정, 언론사 간 추적 미지원 |
| **GDELT** | 오픈데이터 | 글로벌 이벤트/뉴스 DB, 실시간 업데이트 | 원시 데이터 제공, UI/UX 없음 |
| **NewsDiffs** | 오픈소스 | 기사 수정 이력 추적 | 단일 기사 변경 추적, 전파 추적 아님 |
| **Brand24** | 상용 (SMB) | 미디어 모니터링, 감성 분석 | 브랜드 모니터링 중심 |

### 2.3 News Origin의 차별점
1. **First-mover Detection**: 최초 보도 언론사/기자 자동 식별
2. **Citation Chain**: 인용/참조 관계 시각화 (A → B → C)
3. **Explosion Point**: 동시다발 보도 시점 자동 감지
4. **News Lifecycle**: 생성 → 확산 → 소멸 전 과정 시각화
5. **Isolation Detection**: 연결 없이 독립적으로 작성된 기사 식별
6. **개인 사용자 친화적**: 엔터프라이즈가 아닌 일반 사용자 대상

---

## 3. Technology Stack

### 3.1 Frontend

| 항목 | 선택 | 근거 |
|------|------|------|
| **Framework** | React 18 + TypeScript | 생태계 최대, 시각화 라이브러리 호환성 |
| **Build Tool** | Vite | 빠른 개발 서버, HMR |
| **UI Library** | shadcn/ui + Tailwind CSS | 무료, 커스터마이징 자유도 최고, 가장 널리 사용 |
| **Graph View** | AntV G6 v5 | 전파 그래프 전용 - 읽기 전용에 최적화된 강력한 그래프 시각화 |
| **Timeline/Charts** | Apache ECharts (echarts-for-react) | 타임라인 + 밀도 차트 + 통계 차트 올인원 |
| **State Management** | Zustand | 경량, 간단한 API |
| **HTTP Client** | Axios | 인터셉터, 에러 핸들링 |
| **Router** | React Router v6 | 표준 |

#### 시각화 라이브러리 변경 사유 (v0.2.0)

**React Flow 제외 사유:**
React Flow의 핵심 강점은 노드 편집, 드래그 앤 드롭, 커넥션 생성 등 **편집 기능**에 있음. News Origin에서 사용자는 타임라인을 **수정할 필요가 없으므로** 편집 중심 라이브러리는 과도하며, 읽기 전용에 특화된 라이브러리가 적합함.

**AntV G6 v5 선택 근거 (전파 그래프용):**

| 항목 | 상세 |
|------|------|
| GitHub Stars | 11K+ |
| 라이선스 | MIT |
| 핵심 강점 | 10+ 내장 레이아웃 (radial tree, force-directed, dagre 등) |
| 렌더링 | Canvas/SVG/WebGL + WebGPU/WASM 가속 지원 |
| 읽기 전용 지원 | 편집 비활성화 + hover/click/zoom/pan 인터랙션 유지 |
| 클러스터링 | 내장 커뮤니티 감지 알고리즘 → **폭발 시점 표현에 최적** |
| 유지보수 | Ant Group 지원, 매우 활발 (최근 1주일 내 업데이트) |
| React 통합 | @antv/g6 직접 사용 또는 Graphin 래퍼 |
| 테마 | Light/Dark 테마, 20+ 컬러 팔레트 |

**Apache ECharts 선택 근거 (타임라인 + 차트용):**

| 항목 | 상세 |
|------|------|
| GitHub Stars | 60K+ |
| 라이선스 | Apache 2.0 |
| 핵심 강점 | **타임라인 컴포넌트 내장** - 시간축 기반 시각화 네이티브 지원 |
| 지원 차트 | tree, graph, sankey, bar, line, scatter 등 올인원 |
| 번들 크기 | ~400KB (tree-shaking으로 ~100KB 가능) |
| 모바일 | 최적화된 모바일 런타임 (4KB), 반응형 |
| 유지보수 | Apache Foundation, 매우 활발 |
| React 통합 | echarts-for-react (안정적인 래퍼) |
| 성능 | Progressive rendering, 100K+ 데이터 포인트 처리 |

**이 조합으로 대체되는 기존 라이브러리:**

| 기존 | 대체 | 이유 |
|------|------|------|
| React Flow | AntV G6 | 읽기 전용 그래프에 특화, 클러스터링 내장 |
| React Chrono | Apache ECharts (timeline) | 타임라인 내장, 차트와 통합 |
| Recharts | Apache ECharts (charts) | 동일 라이브러리로 통합, 차트 종류 풍부 |

**검토했으나 제외한 라이브러리:**

| 라이브러리 | Stars | 제외 사유 |
|-----------|-------|-----------|
| React Flow | 35K | 편집 기능 중심, 읽기 전용에 과도 |
| Reagraph | 11.6K | WebGL 전용으로 유연성 제한, 타임라인 미지원 |
| Cytoscape.js | 10.8K | 타임라인 미지원, API 스타일 구식 |
| Sigma.js | - | v3 베타, 스타일 노드 성능 저하 (5K+ 노드) |
| D3 직접 사용 | 110K | React 통합 복잡도 높음, 개발 비용 과다 |
| Visx (Airbnb) | 20K | 저수준 D3 래퍼, 그래프 기능 제한적 |
| vis.js Timeline | 2.3K | React 18 호환성 불안정 |
| KronoGraph | - | 상용 (유료) |
| react-d3-tree | 1.2K | 500+ 노드 성능 문제 (1분 프리징), 트리만 지원 |
| Nivo | - | 네트워크/트리 그래프 미특화, 타임라인 없음 |

### 3.2 Backend

| 항목 | 선택 | 근거 |
|------|------|------|
| **Runtime** | Python 3.11+ | NLP/크롤링 생태계 최강 |
| **Framework** | FastAPI | 비동기 지원, 자동 API 문서(Swagger/ReDoc), 타입 안전성 |
| **Task Queue** | Celery + Redis | 크롤링/분석 비동기 처리 |
| **ORM** | SQLAlchemy 2.0 | 비동기 지원, 표준 |

### 3.3 News Crawling & NLP

| 항목 | 선택 | 근거 |
|------|------|------|
| **기사 추출** | trafilatura (메인) + newspaper4k (폴백) | trafilatura: 벤치마크 최고 정확도 (F1 0.883), Apache 2.0 |
| **뉴스 검색** | Google News RSS (무료) + GNews API (보조) | 무료, 무제한, 한국어 지원 |
| **텍스트 유사도** | sentence-transformers (`paraphrase-multilingual-mpnet-base-v2`) | 다국어 시맨틱 유사도, Apache 2.0 |
| **중복 탐지** | datasketch (MinHash + LSH) | 대규모 근사 중복 탐지, MIT, 수백만 건 처리 |
| **한국어 형태소** | kiwipiepy | 빠른 속도, 사전+비지도 학습 결합 |
| **기본 유사도** | scikit-learn (TF-IDF + cosine) | 빠른 기본 비교, CPU만 사용 |

### 3.4 Data & Cache

| 항목 | 선택 | 근거 |
|------|------|------|
| **Primary DB** | PostgreSQL 15 | 관계형 데이터 + JSONB, 전문 검색 |
| **Vector DB** | **Qdrant** | 전용 벡터 DB - 임베딩 저장/유사도 검색 특화 |
| **Cache / Broker** | Redis 7 | Celery 브로커 겸용, 검색 결과 캐시 |

#### Vector DB 변경 사유 (v0.2.0)

**pgvector 대신 Qdrant를 선택한 이유:**

| 비교 항목 | pgvector | Qdrant |
|-----------|----------|--------|
| 유형 | PostgreSQL 확장 | 전용 벡터 DB |
| 라이선스 | PostgreSQL License | Apache 2.0 |
| 언어 | C (PostgreSQL) | **Rust** (고성능) |
| GitHub Stars | 13K+ | **28K+** |
| 768-dim 지연시간 | 가변적 | **20-50ms p50** |
| 메타데이터 필터링 | SQL WHERE (강력) | **전용 필터 (최소 성능 영향)** |
| 스케일 | ~수백만 (수초 지연) | **수백만~수십억** |
| 양자화 | 미지원 | **Scalar quantization (4-8x 메모리 절감)** |
| Docker 지원 | PostgreSQL 내 | **프로덕션-레디 Docker 이미지** |
| 비동기 Python | asyncpg 활용 | **네이티브 async 클라이언트** |

**검토했으나 제외한 Vector DB:**

| DB | Stars | 제외 사유 |
|----|-------|-----------|
| ChromaDB | 25K | 5천만 벡터 이상 비권장, 프로토타이핑 특화 |
| Milvus | 40K | Docker Compose 프로덕션 비권장 (K8s 필요), 운영 복잡도 높음 |
| Weaviate | 8K | 클라우드 비용 높음, GraphQL 불필요한 복잡도, K8s 권장 |
| pgvector | 13K | 전용 DB 대비 성능/스케일 한계, 양자화 미지원 |

**Qdrant 핵심 강점 (News Origin 관점):**
- 기사 발행일, 언론사, 카테고리 등 **메타데이터 필터링과 벡터 검색을 동시에** 수행 → 특정 기간/언론사별 유사 기사 검색에 최적
- Rust 기반 고성능 → 사용자 요청 시 실시간 유사도 검색 가능
- 양자화 지원 → 비용 효율적으로 대규모 기사 임베딩 저장
- Docker Compose에서 프로덕션 수준으로 운영 가능

### 3.5 Infrastructure

| 항목 | 선택 | 근거 |
|------|------|------|
| **Container** | Docker Compose | 로컬 개발 + 배포 |
| **Reverse Proxy** | Nginx | 정적 파일 서빙, API 프록시, SSL |
| **Process Manager** | Supervisor (컨테이너 내) | Celery worker 관리 |

---

## 4. Architecture

### 4.1 System Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                       Nginx (80/443)                          │
│               Static Files + Reverse Proxy                    │
├───────────────────────┬───────────────────────────────────────┤
│                       │                                       │
│   React SPA           │    FastAPI (/api/*)                   │
│   (Frontend)          │    (Backend)                          │
│                       │         │                             │
│   ┌─────────────┐    │    ┌────┴────┐                        │
│   │ AntV G6     │    │    │ Celery  │ ← Redis (Broker)      │
│   │ (Graph)     │    │    │ Workers │                        │
│   ├─────────────┤    │    └────┬────┘                        │
│   │ ECharts     │    │         │                             │
│   │ (Timeline)  │    │    ┌────┴──────────────────┐          │
│   └─────────────┘    │    │                       │          │
│                       │    │  PostgreSQL      Qdrant         │
│                       │    │  (Relational)    (Vectors)      │
│                       │    │                       │          │
│                       │    └───────────────────────┘          │
└───────────────────────┴───────────────────────────────────────┘
```

### 4.2 Data Flow

```
사용자 입력 (URL 또는 기사 제목)
        │
        ▼
[1] 기사 식별 (URL → 직접 크롤링 / 제목 → Google News 검색 → 사용자 확인)
        │
        ▼
[2] 원본 기사 분석 (trafilatura로 본문/메타데이터 추출)
        │
        ▼
[3] 임베딩 생성 + Qdrant 저장 (sentence-transformers → Qdrant)
        │
        ▼
[4] 유사 기사 검색 (Google News RSS + GNews API + Qdrant 유사도 검색)
        │
        ▼
[5] 수집 기사 분석 (크롤링 → 임베딩 → Qdrant 저장 → 유사도 매트릭스)
        │
        ▼
[6] 타임라인 구성 (발행 시간순 정렬, 유사도 기반 연결/독립 판정, 폭발 감지)
        │
        ▼
[7] 시각화 렌더링 (AntV G6 전파 그래프 + ECharts 타임라인/차트)
```

### 4.3 Core Algorithm: 기사 전파 추적

```
1. 원본 기사 임베딩 생성 (sentence-transformers)
2. Qdrant에 임베딩 저장 (메타데이터: 발행일, 언론사, 카테고리)
3. 검색 엔진으로 유사 기사 수집 (키워드 추출 → Google News RSS/GNews)
4. 수집된 기사별 임베딩 생성 → Qdrant 저장
5. Qdrant 벡터 검색으로 유사도 매트릭스 계산
6. 유사도 임계값 기반 그룹핑:
   - similarity >= 0.90: 동일 기사 (재게시/전재)
   - 0.75 <= similarity < 0.90: 파생 기사 (재작성)
   - 0.60 <= similarity < 0.75: 관련 기사
   - similarity < 0.60: 독립 기사
7. 발행 시간순 정렬 → 전파 방향 추론
8. 폭발 시점 감지:
   - 단위 시간(1시간) 내 유사 기사 수 급증 감지
   - 임계값: 기사 총 수 대비 비율 기반 동적 설정
```

---

## 5. Folder Structure

```
news-origin/
├── docs/                           # 프로젝트 문서
│   ├── implementation-plan.md      # 본 문서
│   └── api-spec.md                 # API 명세 (추후)
│
├── backend/                        # Python Backend
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/                    # DB 마이그레이션
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI 앱 엔트리포인트
│   │   ├── config.py               # 환경 설정
│   │   ├── api/                    # API 라우터
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── articles.py     # 기사 관련 API
│   │   │   │   ├── search.py       # 검색 API
│   │   │   │   ├── timeline.py     # 타임라인 API
│   │   │   │   └── trends.py       # 트렌드/통계 API
│   │   │   └── deps.py             # 의존성 주입
│   │   ├── core/                   # 핵심 비즈니스 로직
│   │   │   ├── __init__.py
│   │   │   ├── crawler.py          # 뉴스 크롤링 엔진
│   │   │   ├── analyzer.py         # 기사 유사도 분석
│   │   │   ├── timeline.py         # 타임라인 구성 로직
│   │   │   └── detector.py         # 폭발 시점 감지
│   │   ├── models/                 # DB 모델 (SQLAlchemy)
│   │   │   ├── __init__.py
│   │   │   ├── article.py
│   │   │   ├── timeline.py
│   │   │   └── search_log.py
│   │   ├── schemas/                # Pydantic 스키마
│   │   │   ├── __init__.py
│   │   │   ├── article.py
│   │   │   ├── timeline.py
│   │   │   └── search.py
│   │   ├── services/               # 외부 서비스 연동
│   │   │   ├── __init__.py
│   │   │   ├── news_search.py      # 뉴스 검색 서비스
│   │   │   ├── embedding.py        # 임베딩 서비스
│   │   │   ├── vector_store.py     # Qdrant 벡터 저장소
│   │   │   └── cache.py            # Redis 캐시 서비스
│   │   └── workers/                # Celery 태스크
│   │       ├── __init__.py
│   │       ├── celery_app.py
│   │       └── tasks.py
│   └── tests/                      # 테스트 (요청 시)
│
├── frontend/                       # React Frontend
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── index.html
│   ├── public/
│   └── src/
│       ├── main.tsx                # 앱 엔트리포인트
│       ├── App.tsx
│       ├── components/
│       │   ├── ui/                 # shadcn/ui 컴포넌트
│       │   ├── layout/             # 레이아웃 컴포넌트
│       │   │   ├── Header.tsx
│       │   │   ├── Sidebar.tsx
│       │   │   └── Footer.tsx
│       │   ├── search/             # 검색 관련
│       │   │   ├── SearchBar.tsx
│       │   │   └── ArticleConfirm.tsx
│       │   ├── visualization/      # 시각화 (v0.2.0 변경)
│       │   │   ├── PropagationGraph.tsx   # AntV G6 기반 전파 그래프
│       │   │   ├── TimelineChart.tsx      # ECharts 기반 타임라인 뷰
│       │   │   ├── DensityChart.tsx       # ECharts 기반 밀도 차트
│       │   │   ├── ArticleNode.tsx        # G6 커스텀 노드 (기사 카드)
│       │   │   ├── ExplosionMarker.tsx    # 폭발 시점 마커
│       │   │   ├── LifecycleIndicator.tsx # 기사 수명 단계 표시
│       │   │   └── ViewToggle.tsx         # 그래프/타임라인 뷰 전환
│       │   ├── stats/              # 통계/트렌드
│       │   │   ├── TrendChart.tsx
│       │   │   └── PopularSearches.tsx
│       │   └── common/             # 공통 컴포넌트
│       ├── hooks/                  # 커스텀 훅
│       ├── stores/                 # Zustand 스토어
│       ├── services/               # API 호출
│       ├── types/                  # TypeScript 타입
│       ├── utils/                  # 유틸리티
│       └── styles/                 # 글로벌 스타일
│
├── docker/                         # Docker 설정
│   ├── nginx/
│   │   └── nginx.conf
│   ├── qdrant/                     # Qdrant 설정 (v0.2.0 추가)
│   │   └── config.yaml
│   └── redis/
│       └── redis.conf
│
├── docker-compose.yml              # 전체 서비스 오케스트레이션
├── .env.example                    # 환경변수 템플릿
└── .gitignore
```

---

## 6. UI/UX Design

### 6.1 주요 화면

#### Screen 1: Home / Search
```
┌──────────────────────────────────────────────┐
│  [Logo] News Origin          [Hot Trends]     │
├──────────────────────────────────────────────┤
│                                              │
│         뉴스의 시작을 추적하세요              │
│                                              │
│  ┌──────────────────────────────────────┐    │
│  │   기사 URL 또는 제목을 입력하세요     │    │
│  └──────────────────────────────────────┘    │
│                                              │
│  [최근 검색]  [인기 검색]                     │
│  ├── "삼성 반도체 투자"                       │
│  ├── "AI 규제 법안"                           │
│  └── "부동산 대책"                            │
│                                              │
│  ─── Hot Trends ────────────────────────     │
│  1. 경제 위기 관련 보도 (142건)               │
│  2. AI 기술 발전 (98건)                       │
│  3. 국제 정세 변화 (67건)                     │
└──────────────────────────────────────────────┘
```

#### Screen 2: Article Confirm (기사 제목 입력 시)
```
┌──────────────────────────────────────────────┐
│  <- 뒤로    "삼성 반도체 투자" 검색 결과       │
├──────────────────────────────────────────────┤
│                                              │
│  이 기사를 추적하시겠습니까?                  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  삼성전자, HBM 생산 투자 확대 발표     │  │
│  │ 조선일보 | 2025-02-10 14:30           │  │
│  │ "삼성전자가 차세대 HBM 메모리 생산을    │  │
│  │  위해 10조원 규모의 투자를 발표..."     │  │
│  │                                        │  │
│  │  [이 기사 추적]  [다시 검색]            │  │
│  └────────────────────────────────────────┘  │
│                                              │
└──────────────────────────────────────────────┘
```

#### Screen 3: Timeline View (핵심 화면)
```
┌─────────────────────────────────────────────────────────────────┐
│  <- 뒤로   "삼성전자 HBM 투자"  [Graph View] [Timeline View]    │
├─────────────────────────────────────────────────────────────────┤
│  ┌───── Summary ──────────────────────────────────────────────┐ │
│  │ Total: 47건 | Origin: 연합뉴스 02/10 09:15                │ │
│  │ Fade-out: 02/11 18:00 | Explosion: 02/10 14:00~15:00     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ═══════ Graph View (AntV G6 - Radial Tree Layout) ═══════    │
│                                                                 │
│              [연합뉴스 09:15] <-- Origin                       │
│               ┃                                                 │
│           ┌───╋───────────┐                                     │
│           v   v           v                                     │
│    [조선 10:30] [한겨레 11:00] [MBC 11:20]                     │
│         ┃                ┃                                      │
│         v                v                                      │
│    [SBS 14:00]    [KBS 14:05]                                  │
│         ┃                ┃                                      │
│    ═════╋════════════════╋═══ << Explosion Point >> ═══        │
│         v                v                                      │
│    [매경 14:10] [한경 14:12] [아시아경제 14:15]                │
│    [디지털타임스 14:18] [전자신문 14:20] ...                    │
│                                                                 │
│         ...                                                     │
│                                                                 │
│    [블로터 02/11 10:00] <-- Fade-out                           │
│                                                                 │
│    --- [Isolated Articles] ---                                  │
│    [Reuters 02/10 16:00] (similarity: 68%)                     │
│       "Samsung to boost HBM..."  (독립 작성)                    │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  ═══ Density Chart (ECharts - Area Chart) ═══                  │
│  ▁▂▃▅▇█████▇▅▃▂▁                                              │
│  09  10  11  12  13  14  15  16  17  18  (시간)                │
│                   << Peak >>                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 News Lifecycle 용어 정의

| 단계 | 영문 | 한국어 | 색상 | 설명 |
|------|------|--------|------|------|
| 최초 보도 | **Origin** | 기원 | Green (#22c55e) | 최초 발행된 기사 |
| 확산 초기 | **Spread** | 확산 | Blue (#3b82f6) | 2~5개 언론사 보도 |
| 폭발 시점 | **Explosion** | 폭발 | Red (#ef4444) | 단시간 다수 보도 (임계값 초과) |
| 지속 보도 | **Sustained** | 지속 | Amber (#f59e0b) | 꾸준히 보도 유지 |
| 소멸 | **Fade-out** | 소멸 | Gray (#6b7280) | 더 이상 새 기사 없음 |
| 재점화 | **Resurge** | 재점화 | Purple (#a855f7) | 소멸 후 다시 보도 |
| 독립 기사 | **Isolated** | 독립 | Teal (#14b8a6) | 전파 관계 없이 독립 작성 |

### 6.3 두 가지 View Mode

**1. Graph View (AntV G6)**
- **레이아웃**: Radial Tree (기본) / Force-directed (대안)
- **노드**: 개별 기사 카드 (언론사 로고, 시간, 제목 요약)
- **엣지**: 전파 관계 (유사도 기반, 굵기로 유사도 표현)
- **독립 노드**: 연결선 없이 별도 영역에 표시
- **인터랙션**: hover → 툴팁, click → 상세 패널, zoom/pan
- **색상**: lifecycle 단계별 노드 색상 차등
- **클러스터링**: 폭발 시점 기사들을 자동 그룹핑 (G6 내장 기능)
- **읽기 전용**: 노드/엣지 편집 비활성화

**2. Timeline View (Apache ECharts)**
- **타임라인 축**: 시간순 가로축, 기사 수 세로축
- **데이터 포인트**: 각 기사를 점으로 표시, 클릭 시 상세
- **폭발 시점**: 밀도 급증 구간 하이라이트
- **Lifecycle 밴드**: 배경색으로 Origin/Spread/Explosion/Fadeout 구간 표시
- **독립 기사**: 별도 레인에 표시
- **밀도 차트**: 하단에 시간별 기사 수 area chart

---

## 7. API Design (주요 엔드포인트)

### 7.1 Search & Track

```
POST /api/v1/articles/track
  Body: { "input": "URL 또는 기사 제목" }
  Response: {
    "type": "url" | "title",
    "article": { ... },         // URL인 경우 바로 기사 정보
    "candidates": [ ... ]       // 제목인 경우 후보 기사 목록
  }

POST /api/v1/articles/confirm
  Body: { "article_url": "...", "search_id": "..." }
  Response: {
    "tracking_id": "...",
    "status": "processing"
  }
```

### 7.2 Timeline

```
GET /api/v1/timeline/{tracking_id}
  Response: {
    "origin": { ... },
    "articles": [ ... ],
    "graph": {
      "nodes": [ ... ],         // AntV G6 노드 데이터
      "edges": [ ... ]          // AntV G6 엣지 데이터
    },
    "timeline": {
      "series": [ ... ],        // ECharts 타임라인 시리즈 데이터
      "density": [ ... ]        // ECharts 밀도 차트 데이터
    },
    "explosion_points": [
      { "start": "...", "end": "...", "count": 23 }
    ],
    "lifecycle": {
      "origin_time": "...",
      "fadeout_time": "...",
      "total_articles": 47,
      "peak_hour": "14:00-15:00",
      "peak_count": 23,
      "duration_hours": 32.75,
      "stages": [
        { "stage": "origin", "start": "...", "end": "..." },
        { "stage": "spread", "start": "...", "end": "..." },
        { "stage": "explosion", "start": "...", "end": "..." },
        { "stage": "sustained", "start": "...", "end": "..." },
        { "stage": "fadeout", "start": "...", "end": "..." }
      ]
    },
    "isolated_articles": [ ... ]
  }

GET /api/v1/timeline/{tracking_id}/status
  Response: {
    "status": "processing" | "completed" | "error",
    "progress": 75,
    "articles_found": 32,
    "articles_analyzed": 24
  }
```

### 7.3 Trends & Stats

```
GET /api/v1/trends/hot
  Query: ?period=24h|7d|30d
  Response: { "trends": [ ... ] }

GET /api/v1/trends/popular-searches
  Query: ?limit=20
  Response: { "searches": [ ... ] }

GET /api/v1/stats/overview
  Response: {
    "total_trackings": 1234,
    "total_articles": 56789,
    "active_trackings": 12
  }
```

---

## 8. DB Schema

### 8.1 PostgreSQL (관계형 데이터)

```sql
-- 추적 요청
CREATE TABLE tracking_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    input_text TEXT NOT NULL,
    input_type VARCHAR(10) NOT NULL,     -- 'url' | 'title'
    origin_article_id UUID,              -- 원본 기사 FK
    status VARCHAR(20) DEFAULT 'pending', -- pending/processing/completed/error
    total_articles INT DEFAULT 0,
    progress INT DEFAULT 0,              -- 0-100
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- 기사
CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    summary TEXT,
    author VARCHAR(255),
    publisher VARCHAR(255),              -- 언론사명
    publisher_domain VARCHAR(255),       -- 언론사 도메인
    published_at TIMESTAMPTZ,            -- 발행 시간 (핵심!)
    crawled_at TIMESTAMPTZ DEFAULT NOW(),
    language VARCHAR(10) DEFAULT 'ko',
    qdrant_point_id UUID,                -- Qdrant 벡터 ID 참조
    metadata JSONB DEFAULT '{}'          -- 추가 메타데이터
);

-- 타임라인 엔트리 (추적 요청 <-> 기사 매핑)
CREATE TABLE timeline_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tracking_id UUID NOT NULL REFERENCES tracking_requests(id) ON DELETE CASCADE,
    article_id UUID NOT NULL REFERENCES articles(id),
    similarity_score FLOAT NOT NULL,     -- 원본 대비 유사도 (0.0-1.0)
    similarity_category VARCHAR(20),     -- same/derivative/related/isolated
    lifecycle_stage VARCHAR(20),         -- origin/spread/explosion/sustained/fadeout/isolated
    parent_article_id UUID REFERENCES articles(id), -- 전파 추정 부모 기사
    is_origin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tracking_id, article_id)
);

-- 검색 로그 (통계/트렌드용)
CREATE TABLE search_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    input_type VARCHAR(10),
    result_count INT DEFAULT 0,
    tracking_id UUID REFERENCES tracking_requests(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_articles_published_at ON articles(published_at);
CREATE INDEX idx_articles_publisher ON articles(publisher);
CREATE INDEX idx_articles_qdrant_point_id ON articles(qdrant_point_id);
CREATE INDEX idx_timeline_tracking_id ON timeline_entries(tracking_id);
CREATE INDEX idx_timeline_lifecycle ON timeline_entries(lifecycle_stage);
CREATE INDEX idx_search_logs_created ON search_logs(created_at);
CREATE INDEX idx_search_logs_query ON search_logs USING gin(to_tsvector('simple', query));
```

### 8.2 Qdrant (벡터 데이터)

```
Collection: "article_embeddings"
  Vector: 768 dimensions (paraphrase-multilingual-mpnet-base-v2)
  Distance: Cosine
  Payload (메타데이터):
    - article_id: UUID (PostgreSQL FK)
    - title: string
    - publisher: string
    - published_at: datetime
    - language: string
    - category: string (optional)
```

---

## 9. Implementation Phases

### Phase 1: Foundation (Week 1)
**목표**: 프로젝트 세팅, 인프라 구성, 기본 크롤링

| Task | 상세 |
|------|------|
| 프로젝트 초기화 | 폴더 구조, .gitignore, .env.example |
| Docker Compose | PostgreSQL + Qdrant + Redis + Backend + Frontend + Nginx |
| DB 구성 | PostgreSQL 스키마, Alembic 마이그레이션 |
| Qdrant 초기화 | Collection 생성, 설정 |
| 기본 크롤링 | trafilatura + newspaper4k 통합 크롤러 |
| 뉴스 검색 | Google News RSS 연동 |
| FastAPI 뼈대 | 기본 라우터, 스키마, 에러 핸들링, CORS |

### Phase 2: Core Analysis Engine (Week 2)
**목표**: 임베딩, 유사도 분석, 타임라인 구성

| Task | 상세 |
|------|------|
| 임베딩 서비스 | sentence-transformers 통합 + Qdrant 저장 |
| 유사도 분석 | Qdrant 벡터 검색 기반 기사 비교 |
| 전파 추론 | 시간순 + 유사도 기반 전파 방향 추론 |
| Lifecycle 판정 | Origin/Spread/Explosion/Fadeout 자동 분류 |
| 폭발 감지 | 단위 시간별 기사 수 기반 동적 감지 |
| Celery 파이프라인 | 비동기 크롤링 → 분석 → 결과 저장 |
| GNews API 연동 | 보조 뉴스 검색 소스 |

### Phase 3: Frontend - Search & Graph (Week 3)
**목표**: React 앱, 검색 UI, AntV G6 전파 그래프

| Task | 상세 |
|------|------|
| React 프로젝트 | Vite + TypeScript + shadcn/ui + Tailwind 세팅 |
| 검색 화면 | SearchBar + URL/제목 자동 감지 |
| 기사 확인 화면 | ArticleConfirm 컴포넌트 |
| 진행 상태 표시 | 크롤링/분석 진행률 실시간 표시 |
| Propagation Graph | AntV G6 Radial Tree 레이아웃 |
| 커스텀 노드 | ArticleNode (언론사, 시간, 제목, lifecycle 색상) |
| 노드 인터랙션 | hover 툴팁, click 상세 패널, zoom/pan |
| 폭발 표현 | G6 클러스터링으로 폭발 그룹 표시 |

### Phase 4: Frontend - Timeline & Polish (Week 4)
**목표**: ECharts 타임라인, 통계, 반응형 UI

| Task | 상세 |
|------|------|
| Timeline View | ECharts 시간축 기반 타임라인 |
| Density Chart | ECharts area chart (시간별 기사 밀도) |
| View Toggle | Graph/Timeline 뷰 전환 |
| Lifecycle Band | 배경색으로 lifecycle 단계 구간 표시 |
| Isolated 표시 | 독립 기사 별도 영역 |
| Summary 패널 | 기사 요약 통계 |
| Hot Trends | 인기 검색, 트렌드 (ECharts 차트) |
| 반응형 UI | 모바일/태블릿/데스크톱 |
| 다크 모드 | Tailwind dark mode + G6/ECharts 테마 |

### Phase 5: Integration & Quality (Week 5)
**목표**: 통합 테스트, 성능 최적화, 배포 준비

| Task | 상세 |
|------|------|
| E2E 통합 | URL/제목 입력 → 분석 → 시각화 전체 플로우 |
| 캐싱 전략 | Redis 캐시 (검색 결과, 타임라인 데이터) |
| 에러 핸들링 | 크롤링 실패, 타임아웃, 네트워크 에러 |
| 성능 최적화 | 임베딩 배치 처리, G6 대규모 노드 최적화 |
| Docker 배포 | 전체 서비스 Docker Compose 프로덕션 설정 |
| Nginx SSL | HTTPS 설정 |

---

## 10. Key Technical Decisions & Risks

### 10.1 결정 사항

| 결정 | 선택 | 근거 | 대안 |
|------|------|------|------|
| Backend 언어 | Python | NLP/크롤링 라이브러리 생태계 | Node.js (NLP 생태계 약함) |
| 그래프 시각화 | AntV G6 | 읽기 전용 특화, 클러스터링 내장, GPU 가속 | React Flow (편집 중심), Reagraph (타임라인 없음) |
| 타임라인/차트 | Apache ECharts | 타임라인 내장, 올인원, 60K stars | React Chrono + Recharts (2개 라이브러리 필요) |
| Vector DB | Qdrant | Rust 고성능, Docker 프로덕션, 필터링 최강 | pgvector (스케일 한계), ChromaDB (대규모 비권장) |
| 뉴스 검색 | Google News RSS | 무료 + 무제한 | NewsAPI (프로덕션 유료), GDELT (복잡) |
| 임베딩 모델 | sentence-transformers | 다국어 시맨틱 유사도 최강, Apache 2.0 | TF-IDF only (정확도 낮음) |

### 10.2 리스크 & 대응

| 리스크 | 영향도 | 대응 |
|--------|--------|------|
| 뉴스 사이트 크롤링 차단 | 높음 | User-Agent 로테이션, 지연 시간(2초+), Redis 캐시 활용, 다중 소스 폴백 |
| 발행 시간 정확도 | 높음 | 다중 소스 시간 교차 검증, meta 태그 + OG 태그 + 본문 추출, 크롤링 시간 보조 |
| 유사도 임계값 tuning | 중간 | 초기 수동 검증 샘플 → A/B 테스트 → 점진적 조정, 사용자 피드백 반영 |
| sentence-transformers 속도 | 중간 | Qdrant에 임베딩 사전 저장 (동일 기사 재계산 방지), 배치 처리, GPU 선택적 사용 |
| Google News RSS 불안정 | 중간 | GNews API 폴백, 직접 크롤링 보조, 결과 캐싱 |
| AntV G6 대규모 노드 성능 | 낮음 | GPU 가속 활성화, 노드 가상화, 100+ 노드 시 클러스터링 |

---

## 11. Comment Policy Implementation

본 프로젝트의 주석 정책:

```python
"""
# crawler.py - News Article Crawler Engine
# Version: 0.1.0
# Description: trafilatura/newspaper4k 기반 뉴스 기사 크롤링 및 메타데이터 추출
# Changes:
#   - 0.1.0: Initial implementation with trafilatura + newspaper4k fallback
"""

class NewsCrawler:
    """
    뉴스 기사 크롤링 엔진

    핵심 기능:
    - URL 기반 기사 본문/메타데이터 추출
    - 키워드 기반 유사 기사 검색
    - 발행 시간 추출 및 정규화

    [BUSINESS LOGIC - DO NOT MODIFY]
    크롤링 간격은 최소 2초를 유지해야 함 (robots.txt 준수)
    """

    async def extract_article(self, url: str) -> Article:
        # [CRITICAL] trafilatura 우선, 실패 시 newspaper4k 폴백
        # 이 순서를 변경하면 정확도가 크게 저하됨
        article = trafilatura.extract(url)

        if not article:
            # [FALLBACK] trafilatura 실패 시 newspaper4k 사용
            article = self._newspaper_fallback(url)

        return article
```

---

## 12. Docker Compose Overview

```yaml
services:
  # Frontend (React)
  frontend:
    build: ./frontend
    depends_on: [backend]

  # Backend (FastAPI)
  backend:
    build: ./backend
    depends_on: [postgres, qdrant, redis]
    environment:
      - DATABASE_URL=postgresql+asyncpg://...
      - QDRANT_URL=http://qdrant:6333
      - REDIS_URL=redis://redis:6379

  # Celery Worker
  celery-worker:
    build: ./backend
    command: celery -A app.workers.celery_app worker
    depends_on: [postgres, qdrant, redis]

  # PostgreSQL (관계형 데이터)
  postgres:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # Qdrant (벡터 DB)
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"   # REST API
      - "6334:6334"   # gRPC
    volumes:
      - qdrant_data:/qdrant/storage

  # Redis (Cache + Celery Broker)
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  # Nginx (Reverse Proxy)
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    depends_on: [frontend, backend]

volumes:
  postgres_data:
  qdrant_data:
  redis_data:
```

---

## 13. Open Questions (논의 필요)

1. **한국어 vs 다국어**: 초기 한국어 중심 + 영어 기본 지원으로 시작할지, 처음부터 다국어를 목표로 할지?
2. **뉴스 소스 범위**: 주요 언론사만 할지, 블로그/SNS도 포함할지?
3. **실시간 vs 배치**: 사용자 요청 시 실시간 크롤링 vs 주기적 배치 크롤링?
4. **인증/계정**: 사용자 인증이 필요한지? (검색 이력 저장, 즐겨찾기 등)
5. **폭발 임계값**: 초기 기준값 (예: 1시간 내 10건 이상)?
6. **기사 소멸 기준**: 마지막 기사 이후 몇 시간을 소멸(Fade-out)로 볼지?
7. **GPU 사용**: sentence-transformers 임베딩 생성 시 GPU 서버 활용 여부?

---

## 14. Dependencies Summary

### Backend (Python)
```
fastapi>=0.104.0
uvicorn>=0.24.0
celery>=5.3.0
redis>=5.0.0
sqlalchemy>=2.0.0
alembic>=1.13.0
asyncpg>=0.29.0
trafilatura>=1.8.0
newspaper4k>=0.9.0
sentence-transformers>=2.2.0
scikit-learn>=1.3.0
datasketch>=1.6.0
kiwipiepy>=0.17.0
pydantic>=2.5.0
httpx>=0.25.0
qdrant-client>=1.7.0
```

### Frontend (React)
```
react@18
react-dom@18
typescript@5
vite@5
@antv/g6@5                    # 전파 그래프 (v0.2.0 변경)
echarts@5                     # 타임라인/차트 (v0.2.0 변경)
echarts-for-react@3           # ECharts React 래퍼 (v0.2.0 변경)
zustand
axios
tailwindcss@3
@radix-ui/* (via shadcn/ui)
react-router-dom@6
```

---

## 15. Success Criteria

- [ ] URL 입력 → 기사 크롤링 → 유사 기사 검색 → 시각화 표시 (E2E)
- [ ] 기사 제목 입력 → 후보 기사 표시 → 사용자 확인 → 시각화 표시
- [ ] 최초 출처(Origin) 기사 자동 식별 및 시각적 강조
- [ ] 전파 흐름 그래프 시각화 (AntV G6 Radial Tree)
- [ ] 시간순 타임라인 시각화 (ECharts Timeline)
- [ ] 밀도 차트로 시간대별 기사 볼륨 표시 (ECharts Area)
- [ ] 폭발 시점 자동 감지 및 하이라이트
- [ ] 독립(Isolated) 기사 식별 및 별도 영역 표시
- [ ] 기사 Lifecycle 단계 시각적 구분 (Origin → Spread → Explosion → Fadeout)
- [ ] hover 시 기사 상세 툴팁 / click 시 원문 링크
- [ ] Graph/Timeline 뷰 전환
- [ ] Hot Trends 및 인기 검색어 표시
- [ ] 반응형 UI (모바일/데스크톱)
- [ ] Docker Compose 단일 명령 배포
- [ ] Qdrant 벡터 검색 20-50ms 이내 응답
