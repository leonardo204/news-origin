# News Origin (뉴스 기원 추적)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React](https://img.shields.io/badge/react-19.0-61dafb.svg)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.0+-blue.svg)](https://www.typescriptlang.org/)

뉴스 기사의 최초 출처를 추적하고 전파 경로를 시각화하는 서비스입니다. 기사의 원본과 파생 관계를 분석하여 정보의 흐름을 투명하게 보여줍니다.

## 주요 기능

- **2단계 추적 시스템**:
  - **즉시 추적 (Instant)**: 기존 DB/벡터 데이터에서 빠른 유사 기사 검색 (수초 내 결과)
  - **Live 추적**: Google News RSS 실시간 크롤링 + BERT NER 키워드 추출 + Azure 임베딩으로 정확한 분석
- **기사 출처 추적**: URL 또는 제목으로 뉴스 기사의 최초 출처 탐색
- **전파 경로 시각화**: 그래프 기반의 기사 전파 네트워크 시각화
- **타임라인 분석**: 시간 순서에 따른 기사 확산 과정 추적
- **유사도 분석**: Azure OpenAI text-embedding-3-large 기반의 기사 유사도 측정
- **NER 키워드 추출**: BERT(klue/bert-base) 기반 한국어 엔터티 인식
- **트렌드 분석**: 인기 검색어 및 실시간 트렌드 통계
- **실시간 검색**: 다양한 언론사의 뉴스 기사 통합 검색

## 기술 스택

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL (관계형 데이터), Qdrant (Vector DB)
- **Cache**: Redis
- **Task Queue**: Celery
- **ORM**: SQLAlchemy (async)
- **Migration**: Alembic
- **Testing**: pytest

### Frontend
- **Framework**: React 19
- **Language**: TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **Visualization**: ECharts (차트), G6 (그래프)
- **State Management**: Zustand
- **HTTP Client**: Axios
- **Routing**: React Router v7

### Infrastructure
- **Containerization**: Docker, Docker Compose
- **Reverse Proxy**: Nginx
- **API Documentation**: OpenAPI (Swagger UI)

## 아키텍처

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Browser   │─────▶│    Nginx    │─────▶│   FastAPI   │
│  (React)    │      │   (Proxy)   │      │  (Backend)  │
└─────────────┘      └─────────────┘      └─────────────┘
                                                  │
                    ┌─────────────────────────────┼─────────────────┐
                    │                             │                 │
               ┌────▼────┐                  ┌────▼────┐      ┌────▼────┐
               │PostgreSQL│                 │  Qdrant │      │  Redis  │
               │   (DB)  │                  │(Vector) │      │ (Cache) │
               └─────────┘                  └─────────┘      └─────────┘
                                                  │
                                            ┌────▼────┐
                                            │ Celery  │
                                            │(Worker) │
                                            └─────────┘
```

### 데이터 흐름

1. **기사 추적 요청**: 사용자가 URL 또는 제목 입력
2. **메타데이터 추출**: 웹 크롤러가 기사 본문 및 메타데이터 수집
3. **확인 및 즉시 분석**: 사용자 확인 후 기존 DB/Qdrant에서 빠른 유사 기사 검색
4. **Live 추적 (선택)**: 즉시 결과 확인 후 "Live 추적" 버튼으로 정밀 분석 전환
5. **NER 키워드 추출**: BERT(klue/bert-base) 기반 한국어 엔터티 인식
6. **Vector Embedding**: Azure OpenAI text-embedding-3-large로 1024차원 벡터 생성, Qdrant 저장
7. **유사도 계산**: 다른 기사들과의 cosine similarity 계산
8. **관계 분류**: 동일(same), 파생(derivative), 관련(related) 관계 판정
9. **시각화**: 전파 경로를 그래프와 타임라인으로 표현

## 프로젝트 구조

```
news-origin/
├── backend/                    # FastAPI 백엔드
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/        # API 엔드포인트
│   │   │       ├── articles.py      # 기사 추적
│   │   │       ├── search.py        # 뉴스 검색
│   │   │       ├── timeline.py      # 타임라인
│   │   │       └── trends.py        # 트렌드 분석
│   │   ├── core/
│   │   │   └── crawler.py     # 웹 크롤러
│   │   ├── models/            # SQLAlchemy 모델
│   │   │   ├── article.py
│   │   │   ├── timeline.py
│   │   │   └── search_log.py
│   │   ├── schemas/           # Pydantic 스키마
│   │   ├── services/          # 비즈니스 로직
│   │   │   ├── news_search.py
│   │   │   └── cache.py
│   │   ├── workers/           # Celery 태스크
│   │   │   └── tasks.py
│   │   ├── config.py          # 설정
│   │   └── main.py            # 진입점
│   ├── alembic/               # 데이터베이스 마이그레이션
│   ├── tests/                 # pytest 테스트
│   └── requirements.txt
├── frontend/                   # React 프론트엔드
│   ├── src/
│   │   ├── components/        # 재사용 가능한 컴포넌트
│   │   │   ├── search/              # 검색 관련
│   │   │   ├── visualization/       # 그래프/차트
│   │   │   └── layout/              # 레이아웃
│   │   ├── pages/             # 페이지 컴포넌트
│   │   │   ├── HomePage.tsx
│   │   │   ├── TimelinePage.tsx
│   │   │   ├── TrendsPage.tsx
│   │   │   └── NotFoundPage.tsx
│   │   ├── stores/            # Zustand 상태 관리
│   │   ├── services/          # API 클라이언트
│   │   ├── hooks/             # Custom React Hooks
│   │   ├── lib/               # 유틸리티 함수
│   │   ├── types/             # TypeScript 타입 정의
│   │   └── App.tsx
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
├── docker/                     # Docker 설정
│   └── nginx/
│       └── nginx.conf
├── docs/                       # 문서
├── docker-compose.yml          # 개발 환경
├── docker-compose.prod.yml     # 프로덕션 환경
└── README.md
```

## 설치 및 실행

### Docker Compose 사용 (권장)

#### 개발 환경

```bash
# 저장소 클론
git clone https://github.com/yourusername/news-origin.git
cd news-origin

# 환경 변수 설정
cp backend/.env.example backend/.env
# backend/.env 파일을 편집하여 필요한 값 설정

# 서비스 시작
docker-compose up -d

# 데이터베이스 마이그레이션
docker-compose exec backend alembic upgrade head

# 로그 확인
docker-compose logs -f
```

서비스 접속:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Qdrant Dashboard: http://localhost:6333/dashboard

#### 프로덕션 환경

```bash
# 프로덕션 설정으로 실행
docker-compose -f docker-compose.prod.yml up -d

# 데이터베이스 마이그레이션
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

서비스 접속:
- Application: http://localhost (Nginx를 통한 접속)

### 로컬 개발 환경

#### Backend

```bash
cd backend

# Python 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일 편집

# 데이터베이스 마이그레이션
alembic upgrade head

# 개발 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Celery Worker

```bash
cd backend

# 가상환경 활성화 후
celery -A app.workers.tasks worker --loglevel=info
```

#### Frontend

```bash
cd frontend

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

Frontend: http://localhost:5173

## 환경 변수

### Backend (.env)

```bash
# Application
APP_ENV=development
APP_DEBUG=true
APP_SECRET_KEY=your-secret-key-here
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/news_origin

# Qdrant (Vector Database)
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_COLLECTION=news_articles

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0

# Embedding
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSION=384

# External API
GNEWS_API_KEY=your-gnews-api-key

# Crawler
CRAWL_DELAY_SECONDS=1.0
CRAWL_MAX_CONCURRENT=5
CRAWL_USER_AGENT=Mozilla/5.0 (compatible; NewsOriginBot/1.0)

# Similarity Thresholds
SIMILARITY_SAME_THRESHOLD=0.95
SIMILARITY_DERIVATIVE_THRESHOLD=0.85
SIMILARITY_RELATED_THRESHOLD=0.70
```

### Frontend (.env)

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## API 엔드포인트

### 기사 추적
- `POST /api/articles/track` - 기사 추적 시작 (URL 또는 제목)
- `POST /api/articles/confirm` - 기사 확인 후 추적 시작 (즉시 분석 기본, tracking_type 선택 가능)
- `POST /api/articles/live-track` - 즉시 추적 → Live 추적 전환
- `GET /api/articles/{id}` - 기사 상세 정보 조회

### 타임라인
- `GET /api/timeline/{tracking_id}` - 타임라인 데이터 조회 (tracking_type 포함)
- `GET /api/timeline/{tracking_id}/status` - 추적 상태 확인 (tracking_type 포함)

### 검색
- `GET /api/search/news?q={query}` - 뉴스 기사 검색

### 트렌드
- `GET /api/trends/hot` - 인기 트렌드 조회
- `GET /api/trends/stats` - 통계 개요
- `GET /api/trends/popular-searches` - 인기 검색어

### 시스템
- `GET /health` - 헬스 체크

자세한 API 명세는 http://localhost:8000/docs 에서 확인할 수 있습니다.

## 테스트

### Backend 테스트

```bash
cd backend

# 전체 테스트 실행
python -m pytest tests/ -v

# 커버리지 포함
python -m pytest tests/ --cov=app --cov-report=html

# 특정 테스트 파일 실행
python -m pytest tests/test_articles.py -v
```

### Frontend 테스트

```bash
cd frontend

# 단위 테스트 실행
npm run test

# 타입 체크
npx tsc --noEmit

# Lint 검사
npm run lint
```

## 데이터베이스 마이그레이션

```bash
cd backend

# 새 마이그레이션 생성
alembic revision --autogenerate -m "description"

# 마이그레이션 적용
alembic upgrade head

# 롤백
alembic downgrade -1

# 마이그레이션 히스토리
alembic history
```

## 개발 가이드

### 코드 스타일
- Backend: PEP 8 (Black formatter 사용 권장)
- Frontend: ESLint + Prettier 설정 준수

### 브랜치 전략
- `main`: 프로덕션 배포 브랜치
- `develop`: 개발 통합 브랜치
- `feature/*`: 기능 개발 브랜치
- `bugfix/*`: 버그 수정 브랜치

### 커밋 메시지
```
type: subject

body (optional)

footer (optional)
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## 성능 최적화

- **Redis 캐싱**: 검색 결과 및 트렌드 데이터 캐싱
- **Vector 인덱싱**: Qdrant HNSW 인덱스 사용
- **비동기 처리**: Celery를 통한 무거운 작업 비동기 처리
- **데이터베이스 인덱싱**: 자주 조회되는 컬럼에 인덱스 적용
- **프론트엔드 최적화**: Code splitting, lazy loading 적용

## 보안

- **CORS 설정**: 허용된 origin만 API 접근 가능
- **Rate Limiting**: API 요청 제한 (구현 예정)
- **입력 검증**: Pydantic을 통한 엄격한 입력 검증
- **SQL Injection 방지**: SQLAlchemy ORM 사용
- **XSS 방지**: React의 자동 이스케이핑

## 문제 해결

### Docker 컨테이너가 시작되지 않을 때
```bash
# 로그 확인
docker-compose logs backend
docker-compose logs frontend

# 컨테이너 재시작
docker-compose restart

# 완전히 재구성
docker-compose down -v
docker-compose up -d --build
```

### 데이터베이스 연결 오류
- PostgreSQL 컨테이너가 실행 중인지 확인
- `DATABASE_URL` 환경 변수 확인
- 포트 충돌 확인 (5432)

### Qdrant 연결 오류
- Qdrant 컨테이너 실행 상태 확인
- `QDRANT_HOST`, `QDRANT_PORT` 환경 변수 확인
- Collection이 생성되었는지 확인

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 기여

기여는 언제나 환영합니다. Pull Request를 보내기 전에 다음을 확인해주세요:

1. 코드 스타일 가이드 준수
2. 테스트 작성 및 통과
3. 문서 업데이트 (필요시)
4. 커밋 메시지 규칙 준수

## 문의

프로젝트와 관련된 문의사항은 Issues를 통해 남겨주세요.

---

**Note**: 이 프로젝트는 뉴스 기사의 출처 추적 및 정보 흐름 분석을 목적으로 하며, 언론의 투명성과 정보의 신뢰성 향상에 기여하고자 합니다.
