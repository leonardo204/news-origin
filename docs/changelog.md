# Changelog

주요 변경사항 이력. 최신순 정렬.

---

## 2026-03-03

### fix: NER 모델 quality gate를 절대 임계값 + 비회귀 방식으로 변경
- **문제**: F1 diff 기반 승격 기준(+1%p)이 고성능 구간(0.93+)에서 달성 불가 → v20260226 이후 모든 모델 승격 실패
- **변경**: `should_promote()` 판정 기준 전환
  - 기존: `new_f1 >= current_f1 + min_improvement` (diff 기반, 기본 1%p)
  - 변경: `new_f1 >= min_f1_threshold` (절대 임계값, 기본 0.90) AND `new_f1 >= current_f1` (비회귀)
- **설정**: `config.py`에 `ner_min_f1_threshold` 추가 (기존 `ner_min_f1_improvement` 대체)
- **수동 조치**: v20260303 (F1=0.9436) 수동 승격 (v20260226 대비 +0.42%p)
- **수정 파일**: `model_manager.py`, `finetune_bert_ner.py`, `report_generator.py`, `config.py`

---

## 2026-02-27

### fix: email_sender.py — summary가 None일 때 plain text 이메일 생성 실패
- **문제**: `send_report_email()`에서 `summary`가 `None`이면 `"\n".join(plain_parts)`에서 TypeError 발생
- **원인**: MLOps 리포트에서 GPT narrative 생성 실패 시 summary=None으로 전달 가능
- **수정**: `plain_parts.append(summary or "")` — None 방어
- **수정 파일**: `email_sender.py`

---

## 2026-02-26

### fix: finetune 컨테이너 SMTP 환경변수 누락 — MLOps 리포트 이메일 미발송
- **문제**: Fine-tuning 완료 후 MLOps 리포트는 정상 생성되나 "SMTP 미설정 — 미발송" 상태
- **원인 1**: `docker-compose.prod.yml`의 finetune 컨테이너에 SMTP 환경변수 미설정 (수동 실행 시)
- **원인 2 (근본)**: `trigger_bert_finetune` Docker SDK `env_keys` 리스트에 SMTP 변수 누락 (자동 실행 시)
  - Docker SDK는 `docker-compose.prod.yml`을 읽지 않고, celery-worker의 `os.environ`에서 `env_keys` 리스트의 변수만 복사
  - SMTP_HOST 등이 리스트에 없어 finetune 컨테이너에 전달되지 않음
- **수정**: `tasks.py` `env_keys`에 SMTP 7개 + CORS_ORIGINS 추가, `docker-compose.prod.yml`도 동일하게 유지
- **수정 파일**: `tasks.py`, `docker-compose.prod.yml`

---

## 2026-02-25

### feat: Fine-tuning 완료 후 MLOps 리포트 자동 생성 + 이메일 발송
- **목적**: Fine-tuning 완료 시 (품질 게이트 통과/실패 모두) 학습 결과 리포트를 자동 생성하고 관리자에게 이메일로 발송
- **`report_generator.py` (v0.3.0)**: `generate_finetune_report()` + `_generate_finetune_narrative()` 추가
  - 동기 wrapper — finetune 컨테이너에서 직접 호출, 자체 async engine 생성/폐기 (mlops_insight.py 패턴)
  - content_json: training(설정) + evaluation(F1/Precision/Recall) + quality_gate(승격 여부) + deployment_insight + GPT-5 narrative
  - 승격 시 severity="info", 거부 시 severity="warning"
  - GPT-5 비전문가 관리자용 한국어 500자 내러티브 (빈 응답 시 2회 재시도)
- **`finetune_bert_ner.py`**: 품질 게이트 판정 후 리포트 생성 호출 (try/except로 감싸 실패 시 fine-tuning 결과에 무영향)
- **`email_sender.py`**: `type_label`에 `"mlops": "MLOps 학습 리포트"` 추가
- **`ReportsPage.tsx`**: MLOps 리포트 타입 지원
  - TYPE_LABELS + 필터 드롭다운에 `mlops` 추가
  - 보라색 뱃지 + Activity 아이콘
  - `FinetuneReportSection` 컴포넌트: 학습 설정, 평가 결과(3열 F1/P/R), 품질 검증(승격 아이콘), 배포 인사이트(보라색 카드)
- **수정 파일**: `report_generator.py`, `finetune_bert_ner.py`, `email_sender.py`, `ReportsPage.tsx`

---

## 2026-02-24

### feat: NER Fine-tuning 파이프라인 전면 개선 (v0.4.0)
- **문제**: v0005 모델이 v0004 대비 F1 하락 (0.8372 → 0.8006)으로 배포 거부. 원인: 매 학습마다 새 샘플만 사용하고 base 모델부터 처음부터 학습 → 이전 지식 소실
- **Phase 1 — 핵심 수정**:
  - **누적 학습 데이터 사용**: `load_training_data()`에서 `is_used_for_training == False` 필터 제거 → 전체 누적 데이터 사용
  - **Entity-level 메트릭 (seqeval)**: 토큰 단위 F1 → `seqeval` 엔터티 단위 F1로 전환, `NerModelVersion.metric_type` 컬럼 추가 (Alembic 012)
  - **메트릭 전환 처리**: `should_promote()`에서 이전 모델 `metric_type != "entity"`이면 "첫 모델" 경로 적용 (직접 비교 불가)
  - **학습 데이터 상한**: `ner_training_max_samples=2000`, `gpt_quality_score DESC` 정렬로 고품질 우선 선택
  - **학습 품질 임계값 분리**: `ner_training_min_quality=0.5` (기존 수집 임계값 0.1과 분리)
- **Phase 2 — 고도화**:
  - **Continual Learning**: `ner_continual_learning=True` 시 이전 active 모델에서 이어서 학습, 라벨 불일치 시 자동 fallback
  - **Adaptive Learning Rate**: base 모델 5e-5, fine-tuned 이어 학습 2e-5
  - **Early Stopping**: `ner_max_epochs=10`, `ner_early_stopping_patience=2`, HuggingFace `EarlyStoppingCallback`
  - **Stratified Train/Val Split**: 엔터티 유형 기반 층화 분할, 희소 클래스 < 2건 시 random fallback
- **설정 추가** (`config.py`): `ner_training_max_samples`, `ner_training_min_quality`, `ner_continual_learning`, `ner_learning_rate_base`, `ner_learning_rate_finetune`, `ner_max_epochs`, `ner_early_stopping_patience`
- **모델 버전 체계 변경**: 순차 번호 `v0001` → 날짜 기반 `v20260224` (같은 날 재학습 시 `v20260224_2`), 기존 버전과 호환
- **수정 파일**: `finetune_bert_ner.py`, `config.py`, `model_manager.py`, `ner_training.py`, `012_add_metric_type.py`

### feat: 트래픽 방문자 지역 계층 구조 — 국가 > 도시/구
- **백엔드**: ip-api.com 필드에 `regionName`, `district` 추가 → "서울 광진구" 형태 지역명 조합
  - 도시별 `unique_ips` 집계 추가, cities 제한 5→10개
- **프론트엔드**: 국가별 클릭 펼침/접힘 UI (ChevronDown/Right), 하위 도시별 요청수 + IP수 + 프로그레스 바
- **기존 GeoIP 캐시**: Redis 24h TTL 만료 후 새 필드 포함 데이터로 자동 갱신
- **수정 파일**: `admin.py`, `TrafficPage.tsx`

---

## 2026-02-23

### fix: 기사 published_at 날짜 오표시 — trafilatura 날짜 추출 버그 방지
- **문제**: trafilatura 이전 버전이 한국 뉴스 사이트에서 `published_at`을 `2026-02-01`로 잘못 추출
  - 386개 기사가 실제 발행일(2/20~2/23)과 다른 날짜(2/1)로 DB에 저장됨
  - RSS 피드에서 정확한 `published_at`을 제공하지만 크롤러 날짜만 사용하여 무시됨
- **수정 1** (`tasks.py` v0.11.0): RSS `published_at` 폴백 추가
  - `url_published_at_map` 생성 — RSS 날짜를 기본으로 사용
  - trafilatura 날짜가 없거나 RSS 날짜와 7일 이상 차이나면 RSS 날짜로 대체
- **수정 2** (`crawler.py` v0.2.0): `_parse_date()` 이상치 검증
  - 현재 시각 대비 7일 이상 과거 날짜는 `None` 반환하여 RSS 폴백 유도
- **수정 3** (`requirements.txt`): `trafilatura>=1.8.0` → `trafilatura==2.0.0` 버전 고정
- **데이터 보정**: 386개 기사의 `published_at`을 `created_at`으로 보정 (SQL UPDATE)
- **수정 파일**: `tasks.py`, `crawler.py`, `requirements.txt`

### fix: Fine-tuning 이벤트 루프 충돌 + Docker Redis 연결 수정
- **문제 1**: `promote_model()`이 호출자의 `session_factory`를 재사용하나, 내부에서 `asyncio.new_event_loop()` 생성 → 다른 루프에 바인딩된 커넥션 풀 사용 → `Future attached to a different loop` 에러
  - 심볼릭 링크 전환은 성공하지만 DB 상태 업데이트(active/retired) 실패
- **문제 2**: finetune 컨테이너에 `CELERY_BROKER_URL` 미설정 → `redis://localhost:16379/1` 기본값 사용 → Docker 네트워크에서 Redis 연결 실패 → reextract 태스크 트리거 불가
- **수정 1** (`model_manager.py` v0.2.0): `promote_model()`이 자체 엔진/세션 생성·폐기 — 외부 session_factory 의존 제거
- **수정 2** (`finetune_bert_ner.py` v0.3.0): `_qg_factory` 공유 제거, DB 작업마다 독립 엔진 생성 패턴 적용
- **수정 3** (`docker-compose.prod.yml`): finetune 컨테이너에 `CELERY_BROKER_URL=redis://redis:6379/1` + `redis` depends_on 추가
- **수정 파일**: `model_manager.py`, `finetune_bert_ner.py`, `docker-compose.prod.yml`

### refactor: Fine-tuning 24시간 중복 방지 조건 삭제 + v0004 수동 트리거
- **변경** (`tasks.py`): `check_training_readiness`에서 24시간 내 모델 생성 여부 확인 로직 제거
  - 기존: `NerModelVersion.created_at >= now - 24h` 조건으로 중복 트리거 방지
  - 변경: 임계치 초과 시 항상 자동 트리거 (finetune 컨테이너 자체가 중복 실행 방지)
- **수동 트리거**: v0004 학습 시작 (Train 273건, Val 69건, unused 361건)
- **수정 파일**: `tasks.py`

### fix: 트렌드 토픽 기간별 필터링 미작동 수정 (v0.7.0)
- **문제**: 24h/7d/30d 기간 전환 시 동일한 클러스터 결과 반환
  - `ORDER BY created_at DESC LIMIT N`으로 모든 기간이 최근 1~2일 기사만 클러스터링
  - 7d의 1,000건도 실제로는 최근 1.5일치, 30d의 1,500건도 최근 2일치만 포함
- **수정** (`trend_clustering.py` v0.7.0): 일균등 샘플링(stratified time sampling) 도입
  - 24h: 기존 방식 유지 (최신 500건)
  - 7d/30d: `_stratified_time_sample()` — 날짜별 버킷으로 분배, 각 날짜에서 균등 추출
    - 7d: 7일 × ~143건/일 = 1,000건, 30d: 30일 × ~50건/일 = 1,500건
  - `total_articles` 별도 COUNT 쿼리로 실제 기간 내 전체 기사 수 표시
- **결과**: period별 확연히 다른 클러스터 토픽
  - 24h: 오늘의 브레이킹 뉴스 (김길리, 함양 산불, 트럼프 관세)
  - 7d: 이번 주 주요 뉴스 (코스피 5900선, 올림픽, 장동혁)
  - 30d: 월간 트렌드 (동계올림픽 전반, 송영길 공천, 경제)
- **수정 파일**: `trend_clustering.py`

---

## 2026-02-22

### fix: BERT NER per-title fallback이 전역 상태 덮어쓰는 버그 수정
- **문제**: BERT NER 모델이 정상 로딩(`_use_bert_ner=True`)된 후, 첫 번째 빈 결과 기사에서 kiwipiepy fallback 호출 시 `_load_kiwi()`가 `_use_bert_ner=False`로 전역 리셋
  - 이후 모든 기사가 kiwipiepy로 처리되어 BERT 모델이 사실상 비활성화
  - 대시보드에 `use_bert: false`로 표시 (실제로는 BERT 로딩 성공 상태)
- **수정** (`keyword_extractor.py`): `_ensure_kiwi()` 메서드 신설 — kiwipiepy lazy 로딩만 수행, `_use_bert_ner` 플래그 유지
  - `extract()`, `extract_batch()`의 per-title fallback에서 `_load_kiwi()` → `_ensure_kiwi()` 전환
  - `_load_kiwi()`는 BERT 완전 실패 시에만 사용 (기존 동작 유지)
- **수정** (`tasks.py`): NER 상태에 `kiwi_loaded` 필드 추가 — kiwipiepy fallback 사용 여부 추적
- **수정 파일**: `keyword_extractor.py`, `tasks.py`

### feat: 서비스 상태 InfoBadge 툴팁 + NER 모델 상태 표시 + 컨테이너별 메모리
- **서비스 InfoBadge**: 개요 페이지 서비스 상태에 각 컨테이너 역할 설명 툴팁 추가 (InfoBadge 재사용)
- **NER 모델 상태**: 워커 `check_worker_memory`에서 Redis에 NER 로딩 상태 저장 → 개요에 5번째 서비스로 표시
  - BERT 정상: 녹색 "v0003 (BERT)", kiwipiepy 폴백: 노란색, 로딩 중: 노란색
- **컨테이너 메모리**: `/api/admin/system`에 Docker SDK로 `newsorigin-*` 컨테이너별 메모리 stats 추가
  - `ThreadPoolExecutor` 병렬 수집 + `asyncio.to_thread` + 12s timeout으로 API 블로킹 방지
  - 시스템 페이지에 프로그레스 바 UI (색상: <60% 초록, 60-80% 노란, >80% 빨간)
  - 컨테이너별 InfoBadge 툴팁 (역할 설명 + 적정 메모리 범위)
- **MLOps 인라인 평가**: kiwipiepy fallback 사유 표시 ("빈 결과 폴백" / "모델 미로딩"), GPT 평가 reasoning 표시
- **수정 파일**: `tasks.py`, `admin.py`, `OverviewPage.tsx`, `SystemPage.tsx`, `MLOpsPage.tsx`

### fix: BERT NER score 임계값 설정화 + Worker 메모리 임계값 상향
- **문제 1**: BERT NER v0003 모델의 confidence score가 0.25~0.50 범위로 출력되나, 하드코딩된 `score < 0.5` 필터에 의해 거의 모든 엔터티 탈락 → 전 기사 kiwipiepy fallback
- **문제 2**: Worker 메모리 ~1.3GB 사용 중 CRITICAL 임계값 950MB로 불필요한 알림 발생 (호스트 11GB 가용)
- **수정 1** (`config.py`): `ner_score_threshold: float = 0.25` 설정 추가
- **수정 2** (`keyword_extractor.py`): 하드코딩 `0.5` → `settings.ner_score_threshold` 참조
- **수정 3** (`tasks.py`): WARN 800→1400MB, CRITICAL 950→1700MB
- **수정 4** (`docker-compose.prod.yml`): celery-worker mem_limit 1536m→2048m, mem_reservation 1024m→1536m
- **수정 파일**: `config.py`, `keyword_extractor.py`, `tasks.py`, `docker-compose.prod.yml`, `CLAUDE.md`

### fix: BERT NER 빈 추출 결과 시 kiwipiepy fallback 추가
- **문제**: BERT NER 모델이 로딩되어 있지만 특정 제목에서 score < 0.5 엔터티만 반환 → 빈 키워드로 저장
  - GPT-5 평가에서 0점, 대시보드 인라인 평가에 "데이터 수집 전" 오표시
- **수정** (`keyword_extractor.py`): `extract()`, `extract_batch()` 에서 BERT 결과가 빈 경우 kiwipiepy fallback
  - kiwipiepy는 lazy 로딩 (BERT 정상 동작 시 메모리 사용 없음)
- **수정** (`MLOpsPage.tsx`): "데이터 수집 전" → "추출 결과 없음"으로 레이블 변경
- **수정 파일**: `keyword_extractor.py`, `MLOpsPage.tsx`

### fix: Beat 스케줄 KST 기준 정합성 수정 — 주간/월간 리포트 실행 시각 오류
- **문제**: `timezone="Asia/Seoul"` 설정으로 crontab 값이 KST로 해석되는데, 주간/월간 리포트가 UTC로 착각하고 `hour=0` 설정
  - 의도: 월요일/매달 1일 09:00 KST → 실제: 00:00 KST에 실행 (9시간 빠름)
  - `_next_cron_run()` 함수도 UTC로 계산하여 대시보드 예상 시간이 beat와 불일치
- **수정 1** (`beat_schedule.py`): 주간/월간 리포트 `hour=0` → `hour=9` (09:00 KST)
- **수정 2** (`admin.py`): `_next_cron_run()` KST 기준 계산으로 변경, `day_of_week` 파라미터 추가
  - 학습 준비 확인: `hour=2`(UTC 착각) → `hour=11`(KST)
  - 키워드 재추출 interval 표시: "13:00 KST" → "04:00 KST"
- **수정 3** (`CLAUDE.md`): datetime timezone 문서 전면 정리 — Beat/DB/표시 각각의 기준 명시
- **수정 파일**: `beat_schedule.py`, `admin.py`, `CLAUDE.md`

### refactor: 관리자 대시보드 '수집' + '통계' → '수집 통계' 통합
- **문제**: '수집'과 '통계' 페이지가 카테고리 분포, 언론사 순위, 일별 수집 추이 등 유사 내용 중복 제공
- **해결**: 두 페이지를 `CollectionStatsPage.tsx`로 통합, 중복 제거
  - 통계의 30일 ECharts 라인 차트 채택 (수집의 14일 심플 바 대체)
  - 통계의 Top 15 언론사 채택 (수집의 Top 10 대체)
  - 수집 고유 기능(스케줄, 피드 소스, 최근 기사) + 통계 고유 기능(개요 카드, 추적 유형) 모두 유지
  - 두 API(`/crawl`, `/stats`) 병렬 호출
- 네비게이션: '수집' + '통계' 2개 → '수집 통계' 1개로 축소
- **삭제**: `CollectionPage.tsx`, `StatsPage.tsx`
- **수정 파일**: `CollectionStatsPage.tsx`(신규), `App.tsx`, `AdminLayout.tsx`

### feat: BERT NER 모델 자동 리로딩 + Fine-tuning 후 키워드 재추출 자동 트리거
- **문제**: Fine-tuning으로 새 모델 승격 후에도 워커가 이전 모델을 계속 사용
  - `KeywordExtractor` 싱글톤이 최초 로딩된 모델을 프로세스 종료까지 유지
  - finetune 컨테이너(별도 프로세스)에서 심볼릭 링크 전환해도 워커에 반영 안 됨
- **해결 1 — 자동 모델 감지** (`keyword_extractor.py`):
  - `_loaded_model_path` 필드로 현재 로딩된 모델 경로 추적
  - `_check_model_changed()` 메서드: `extract()`/`extract_batch()` 호출마다 active 심볼릭 링크 확인
  - 심볼릭 링크 대상이 변경되었으면 `_loaded=False`, `_ner_pipeline=None`으로 리셋 → 다음 호출에서 자동 리로딩
- **해결 2 — 자동 재추출 트리거** (`finetune_bert_ner.py`):
  - `promote_model()` 성공 후 Celery broker로 `reextract_keywords_batch` 태스크 자동 전송
  - 워커가 새 모델로 최근 7일 기사 키워드 자동 재추출
  - webhook 메시지에 "키워드 재추출 태스크 자동 트리거됨" 반영
- **해결 3 — 재추출 후 트렌드 캐시 워밍** (`tasks.py`):
  - `reextract_keywords_batch` 완료 후 트렌드 캐시 무효화 + 3개 기간(24h/7d/30d) 재계산
  - 새 키워드 기반 클러스터가 즉시 반영 (기존: 다음 크롤링까지 최대 30분 지연)
  - 실행 결과(건수, 모델 버전, 완료 시각, 캐시 워밍 여부)를 Redis에 30일간 저장
- **해결 4 — 대시보드 파이프라인 7단계 확장** (`admin.py`, `MLOpsPage.tsx`):
  - "재클러스터링" 스테이지 추가: 재추출 후 캐시 워밍 완료 여부 표시
  - Redis 저장 데이터 기반으로 두 스테이지(재추출/재클러스터링)에 건수·모델·시각 표시
  - 파이프라인 InfoBadge 7단계 설명으로 업데이트
- **수정 파일**: `keyword_extractor.py`, `finetune_bert_ner.py`, `tasks.py`, `admin.py`, `MLOpsPage.tsx`

### fix: BERT NER v0003 키워드 추출 활성화 — float32 직렬화 + 메모리 한도 조정
- **문제 1**: BERT NER 모델이 정상 로딩되었으나, `numpy.float32` 스코어가 JSONB 직렬화 실패
  - `keyword_extractor.py`의 `_extract_with_bert()`에서 반환하는 score가 `numpy.float32` 타입
  - PostgreSQL JSONB 컬럼에 저장 시 `TypeError: Object of type float32 is not JSON serializable`
  - **해결**: `float(ent.get("score", 0))`로 Python native float 변환
- **문제 2**: celery-worker `mem_limit: 1024m`이 BERT NER 로딩 후 부족 (~1.35GB 사용)
  - **해결**: `mem_limit: 1536m`, `mem_reservation: 1024m`으로 상향
- **문제 3**: `reextract_keywords_batch` time_limit이 600s로 5692개 기사 처리에 부족 (실제 ~2078s)
  - **해결**: `soft_time_limit: 3600s`, `time_limit: 3660s`로 상향
- **재추출 실행**: `reextract_keywords_batch`로 최근 7일 5692개 기사 키워드를 BERT NER v0003으로 재추출 완료
  - 기존: 전체 6570개 기사 `kiwipiepy` → 변경 후: 5692개 `bert_ner` + 878개 `kiwipiepy` (7일 이전)
- **참고**: 인라인 평가 활동의 `extraction_method`는 기사 크롤링 시점의 원본 메타데이터를 표시함 (재추출하지 않음)
- **수정 파일**: `keyword_extractor.py`, `tasks.py`, `docker-compose.prod.yml`, `CLAUDE.md`

### fix: MLOps 파이프라인 상태 동기화 — 모델 배포 + 학습 데이터 수집 복구
- **문제 1**: `finetune_bert_ner.py`에서 `promote_model(version)` 호출 시 `session_factory` 미전달
  - 파일시스템 심볼릭 링크(`active→v0003`)는 업데이트되었으나, DB에 `is_active=false, status=ready`로 남아 있음
  - MLOps 대시보드에서 "모델 배포: 대기 중"으로 표시, 현재 모델 "base"로 오표시
  - **해결**: `promote_model(version, session_factory=_qg_factory)` — DB 팩토리 전달하여 DB 상태 동기 업데이트
- **문제 2**: `save_training_sample()`이 `asyncio.new_event_loop()` 중첩으로 실패
  - `collect_ner_training_data` 태스크가 `run_async()` 이벤트 루프 내에서 `save_training_sample()`의 별도 이벤트 루프 생성 시도 → "Cannot run the event loop while another loop is running"
  - 6시간 주기 NER 학습 데이터 수집이 전혀 저장되지 않던 상태
  - **해결**: `save_training_sample()`을 `async def`로 변환, 호출부에서 `await` 사용
- **문제 3**: 파이프라인 상태 로직에서 `ready` 모델 미배포 상태 미감지
  - **해결**: `deploy` 스테이지에 `pending` 상태 추가, 프론트엔드에 보라색 "배포 대기" 뱃지 스타일 추가
- **DB 복구**: v0003 모델 `is_active=true, status='active'`로 수동 업데이트
- **수정 파일**: `ner_training_pipeline.py`, `tasks.py`, `finetune_bert_ner.py`, `admin.py`, `MLOpsPage.tsx`

### feat: Fine-tuning 별도 컨테이너 전환 + 대시보드 모니터링
- **문제**: `trigger_bert_finetune`가 worker 내에서 실행 시 `--pool=solo` 블로킹(~2h) + OOM 위험
- **해결**: Docker SDK로 `newsorigin-finetune` 컨테이너를 detach 모드로 시작하여 워커 블로킹 제거
  - `tasks.py`: `trigger_bert_finetune` — Docker SDK로 컨테이너 시작, 중복 실행 방지, 워커에서 image/network/volume 자동 추출
  - `soft_time_limit` 7200s → 60s (시작만 하고 즉시 반환)
- **Docker 소켓 마운트**: celery-worker + backend에 `/var/run/docker.sock` 마운트, `DOCKER_GID` group_add
- **대시보드 모니터링**: `/api/admin/mlops` 응답에 `finetune_status` 추가
  - Docker SDK로 컨테이너 상태(running/exited/not_found), 시작/종료 시각, exit_code, 로그 tail 조회
  - 파이프라인 finetune 스테이지에 컨테이너 running 상태 자동 반영
- **프론트엔드**: MLOpsPage에 Fine-tuning 컨테이너 상태 카드 추가
  - running 시 펄스 애니메이션 + 보라색 테두리, exited 시 성공/실패 아이콘
  - 시작/종료 시각 KST 표시, 최근 로그 10줄 미리보기
- **의존성**: `docker>=7.0.0` 추가 (requirements.txt)
- **수정 파일**: `requirements.txt`, `docker-compose.prod.yml`, `tasks.py`, `admin.py`, `MLOpsPage.tsx`, `CLAUDE.md`

### fix: Fine-tuning 컨테이너 실행 오류 3건 수정
- **PermissionError**: 볼륨(`bert_models`) root 소유 → `appuser` 쓰기 불가
  - `tasks.py`: finetune 시작 전 chown init 컨테이너로 볼륨 권한 초기화 (UID 1000)
- **no_cuda TypeError**: `transformers` v5+에서 `no_cuda` 인자 제거됨
  - `finetune_bert_ner.py`: `no_cuda=True` → `use_cpu=True`
- **accelerate ImportError**: `transformers` Trainer가 `accelerate>=1.1.0` 필수 의존
  - `requirements.txt`: `accelerate>=1.1.0` 추가
- **검증**: 수동 트리거 → v0003 학습 완료 (F1=0.734, Precision=0.829, Recall=0.659), Quality gate 통과, 모델 승격 확인
- **수정 파일**: `tasks.py`, `finetune_bert_ner.py`, `requirements.txt`

### fix: check_training_readiness Beat 스케줄 시간대 오류 수정
- **원인**: `crontab(hour=2)` + `timezone="Asia/Seoul"` → 02:00 KST(새벽 2시) 실행, 의도한 11:00 KST가 아님
- **증상**: Beat 컨테이너 시작(02:41 KST) 이후 당일 02:00을 놓쳐 `total_run_count: 0` (한 번도 실행 안 됨)
- **수정**: `crontab(hour=11, minute=0)` — 매일 11:00 KST에 실행
- **CLAUDE.md**: Beat crontab이 KST 기준임을 명확히 기술 (기존 "UTC 기준" 오기 수정)
- **수정 파일**: `beat_schedule.py`, `CLAUDE.md`

### fix: Celery 헬스체크 Redis 하트비트 fallback + 트래픽 KST 그룹핑
- **Celery 헬스체크 개선**: `--pool=solo` 워커가 태스크 실행 중 `inspect().ping()` 응답 불가 → Redis 하트비트 fallback 추가
  - `check_worker_memory` 태스크(5분 주기)에서 `celery:worker:heartbeat` 키를 Redis에 기록 (TTL 600초)
  - 대시보드 overview 엔드포인트: inspect 실패 시 Redis 하트비트 존재 여부로 "정상" 판정
- **트래픽 KST 그룹핑**: 일별/시간별 쿼리에 `timezone('Asia/Seoul')` 적용 — UTC 기준 그룹핑으로 KST 날짜 불일치 해결
- **CLAUDE.md**: Docker 내부 Python 실행 시 `python3` 사용 규칙 명시
- **수정 파일**: `admin.py`, `tasks.py`, `CLAUDE.md`

### feat: 대시보드 개요 페이지 트래픽/MLOps 요약 추가 + Admin 차트 안정화
- **개요 페이지 트래픽 요약**: 오늘 요청수, 에러율(30일), 평균 응답시간(30일), 고유 방문자(30일)
- **개요 페이지 MLOps 요약**: 현재 모델/F1, 평균 품질, 학습 데이터 진행도, 학습 준비도 프로그레스 바
- **개요 섹션 순서 변경**: 기사 통계 → 트래픽 → MLOps → 크롤링 → 서비스 상태 → 시스템 리소스
- **백엔드 `/api/admin/overview`**: traffic(RequestLog 집계) + mlops(모델/학습 데이터) 요약 데이터 추가
- **React error #310 수정**: MLOpsPage, StatsPage, TrafficPage — `useMemo` 훅을 early return 앞으로 이동
- **ECharts 다크테마**: `dark-transparent` 커스텀 테마 등록, 전 관리자 차트에 동적 `theme` prop 적용
- **TrafficPage 일별 차트 재구축**: `useMemo` + `dataZoom` 슬라이더로 기간 탐색, 기존 period 탭 제거
- **수정 파일**: `admin.py`, `OverviewPage.tsx`, `MLOpsPage.tsx`, `StatsPage.tsx`, `TrafficPage.tsx`, `echarts.ts`

---

## 2026-02-21

### fix: Admin 대시보드 트래픽 SQL 오류 + 다크테마 차트 수정 + 모던 스타일 적용
- **SQL GROUP BY 오류 수정**: `admin.py` 트래픽 hourly 쿼리에서 `func.date_trunc("hour", ...)` → `literal_column("'hour'")` 변경 (asyncpg 파라미터 바인딩 불일치 해결)
- **다크테마 차트 가시성**: TrafficPage/MLOpsPage의 ECharts에 `echarts` prop + 동적 `theme` prop 추가, `backgroundColor: 'transparent'` 적용
- **모던 대시보드 스타일**: 전 관리자 페이지 차트를 현대적 스타일로 통일
  - TrafficPage: indigo 그라데이션 area 차트, 투명 배경, 부드러운 곡선 (smooth: 0.4), 도넛 센터 텍스트
  - StatsPage: CSS div 바 차트 → ECharts area 차트로 교체 (일별 기사 수집 추이)
  - MLOpsPage: 하드코딩 `theme="dark"` → 동적 테마 전환, 모든 차트 색상을 테마 변수로 교체
- **수정 파일**: `admin.py`, `TrafficPage.tsx`, `StatsPage.tsx`, `MLOpsPage.tsx`, `echarts.ts`

### fix: recent-articles 프론트엔드 페이지네이션 수정 + CPU 알림 추가
- **recent-articles 버그 수정**: 백엔드 `PaginatedRecentArticles` 응답(`{ items, total, offset, limit }`)을 프론트엔드가 flat array로 취급하던 버그 수정
  - `api.ts`: `data.items` 추출, `offset` 파라미터 전달, `{ items, total }` 반환
  - `useTrendStore.ts`: `recentArticlesTotal` 상태 추가, `loadMoreRecentArticles()` 액션 추가
  - `TrendsPage.tsx`: `.slice(0, 15)` 제거, 총 건수 표시, "더 보기 (N건 남음)" 버튼 추가
- **CPU 사용률 알림**: `alert_detector.py`에 `_check_cpu_usage` 추가 (90% warning, 95% critical, 60분 쿨다운)
  - `config.py`: `alert_cpu_threshold: int = 90` 설정 추가
- **todo-enhancement.md 정리**: P1 API 페이지네이션 ✅, P2 리소스 알림 ✅, 미완료 P3 항목 삭제
- **수정 파일**: `api.ts`, `useTrendStore.ts`, `TrendsPage.tsx`, `config.py`, `alert_detector.py`, `useTrendStore.test.ts`

### feat: 관리자 리포트 시스템 — 정기/비정기 리포트 + 이메일 발송 + GPT-5 내러티브
- **정기 리포트**: 매주 월요일/매달 1일에 자동 생성 (크롤링, 트래픽, MLOps, 시스템, 에러 통계)
  - 기간 비교 (이전 주/월 대비 변동률), 일별 추이, 한국어 카테고리 레이블
  - 상위 언론사 10위, 상위 엔드포인트 10위, 상태코드 분포
  - 시스템 리소스 상세 (CPU/메모리/디스크 총량·사용량·여유)
  - NER 모델 히스토리 + 품질 추이
- **GPT-5 AI 내러티브**: 수집된 통계를 GPT-5가 비전문가 관리자 관점으로 800자 이내 운영 요약 자동 생성
  - 빈 응답 시 자동 재시도 (최대 2회, GPT-5 reasoning 모델 간헐적 빈 content 대응)
- **비정기 리포트**: 10분마다 시스템 알림 체크 (에러율 급증, 트래픽 급증, 디스크/메모리 사용률) → 알림 리포트 자동 생성
  - 카테고리별 대응 가이드 (비전문가 관리자용 권장 조치)
- **이메일 발송**: SMTP HTML 템플릿 — AI 운영 요약 포함, KST 시간 표시, 대시보드 링크 (`https://news.zerolive.co.kr/admin/reports`)
- **게시판 UI**: 전통적인 게시판 스타일 (목록 ↔ 상세 전환)
  - 섹션별 전용 렌더러: 크롤링(카테고리 바 차트, 언론사 랭킹), 트래픽(상태코드 뱃지, 엔드포인트 테이블), MLOps(품질 추이 미니 차트, 모델 히스토리), 시스템(CPU/메모리/디스크 프로그레스 바), 에러(테이블), 알림(대응 가이드 카드)
- **DB 모델**: `admin_reports` 테이블 (report_type, title, summary, content_json, severity, email 상태)
- **Celery Beat**: `generate_weekly_report` (월 09:00 KST), `generate_monthly_report` (1일 09:00 KST), `check_system_alerts` (10분)
- **신규 파일**: `admin_report.py`, `email_sender.py`, `report_generator.py`, `alert_detector.py`, `010_add_admin_reports.py`, `ReportsPage.tsx`
- **수정 파일**: `config.py`, `tasks.py`, `beat_schedule.py`, `admin.py`, `adminApi.ts`, `App.tsx`, `AdminLayout.tsx`, `models/__init__.py`, `docker-compose.prod.yml`

### fix: celery-worker CORS_ORIGINS 환경변수 누락
- **문제**: `docker-compose.prod.yml`의 celery-worker에 `CORS_ORIGINS` 미설정 → 이메일 대시보드 링크가 `http://localhost:10080`으로 생성
- **수정**: celery-worker environment에 `CORS_ORIGINS=${CORS_ORIGINS:-}` 추가

### fix: 트렌드 카테고리 분포 차트 이중 렌더링 — 근본 수정
- **근본 원인**: `ReactECharts`의 `option={{...}}` 내 인라인 `formatter` 함수가 매 렌더마다 새 참조 생성 → `echarts-for-react`의 `fast-deep-equal` 비교 실패 → `notMerge`로 차트 완전 재생성 (애니메이션 2회 실행)
- **트리거**: `useTrendStore()` selector 미사용으로 `recentArticles`, SSE 상태 등 무관한 필드 변경에도 컴포넌트 리렌더
- **수정**: `categoryChartOption`과 `categoryChartEvents`를 `useMemo`로 메모이제이션 → 실제 데이터 변경 시만 차트 갱신
- **수정 파일**: `TrendsPage.tsx`

### feat: Admin 트래픽 대시보드 v2 — GeoIP + IP 필터링 + 차트 개선
- **GeoIP 분포**: ip-api.com 배치 API로 방문자 IP의 국가/도시 분포 집계, Redis 24시간 캐시 (`admin.py`)
- **사설 IP 필터링**: Docker 내부/로컬호스트/예약 IP 자동 제외 (`request_logger.py`: `_is_private_ip()`)
- **경로 필터링**: `/api/admin/*`, `/api/health*`, `/assets/*` 자동 제외 — 실 사용자 트래픽만 수집
- **클라이언트 IP 추출**: CF-Connecting-IP → X-Forwarded-For(첫 번째) → X-Real-IP → direct 우선순위 체인 (`logging_config.py`)
- **차트 개선**: 바 차트 → 그라데이션 에어리어 차트, 상태코드 도넛 중앙 합계, 국가별 플래그 이모지
- **수정 파일**: `admin.py`, `request_logger.py`, `logging_config.py`, `TrafficPage.tsx`

### feat: Admin 트래픽 대시보드
- **HTTP 요청 로그 수집**: FastAPI 미들웨어에서 요청 정보를 비동기 배치 큐에 적재 → 5초/50건마다 DB 일괄 INSERT (`request_logger.py`)
- **DB 모델**: `request_logs` 테이블 (method, path, status_code, duration_ms, client_ip, user_agent, created_at) + 3개 인덱스
- **API**: `/api/admin/traffic` — period(24h/7d/30d) 파라미터로 시간별/일별 트래픽, 상태코드 분포, 엔드포인트 통계, 최근 에러 반환
- **대시보드 UI**: ECharts 차트(시간별 듀얼축, 일별 스택 바, 상태코드 도넛) + 요약 카드 4개 + 엔드포인트/에러 테이블
- **Cleanup 연동**: 기존 `cleanup_old_articles` 태스크에서 90일 초과 request_logs 자동 삭제
- **신규 파일**: `request_log.py`, `request_logger.py`, `009_add_request_logs.py`, `TrafficPage.tsx`
- **수정 파일**: `models/__init__.py`, `logging_config.py`, `main.py`, `admin.py`, `tasks.py`, `adminApi.ts`, `App.tsx`, `AdminLayout.tsx`

### feat: RSS 정책 대응 — 한겨레 NER 학습 제외, 운영 정책, description 활용
- **한겨레 NER 학습 제외**: AI 학습 금지 명시 언론사(한겨레) 기사를 NER 학습 데이터 수집 및 GPT 평가 샘플에서 자동 제외 (`config.py`: `ner_excluded_publishers`, `tasks.py`, `evaluator.py`)
- **운영 정책 페이지**: `/policy` 경로에 서비스 목적, 콘텐츠 이용 방침, AI 학습 정책, 저작권 존중 등 명시, 연락처 이메일 포함 (`PolicyPage.tsx`, `App.tsx`, `Header.tsx`)
- **RSS description 수집**: 언론사 RSS의 description 필드를 파싱하여 크롤링 실패 시 summary 폴백으로 활용 (`news_feed.py`, `tasks.py`)
- **description 미리보기 UI**: 타임라인 카드에 summary 텍스트 표시 (`TimelineChart.tsx`, `timeline.py` 스키마/API)
- **수정 파일**: `config.py`, `tasks.py`, `evaluator.py`, `news_feed.py`, `timeline.py`(스키마+라우트), `App.tsx`, `Header.tsx`, `TimelineChart.tsx`, `types/index.ts`
- **신규 파일**: `PolicyPage.tsx`

### refactor: 추적 결과 화면 정리 + 헤더 레이아웃 변경
- **기사 목록 제거**: 추적 결과(TimelinePage)에서 ArticleList 컴포넌트 제거 (타임라인으로 충분)
- **정책 링크 위치 변경**: Header nav(추적, 트렌드) 우측의 테마토글·현황 영역으로 이동
- **트렌드 이중 로딩 수정**: StrictMode 이중 마운트 시 `loadArticleTrends()` 중복 호출 방지 (`useRef` 가드)
- **수정 파일**: `TimelinePage.tsx`, `Header.tsx`, `TrendsPage.tsx`

### fix: MLOps InfoBadge 추출 방식 설명 보정 + 평가 확장행 단일 열림
- **추출 방식 툴팁 보정**: kiwipiepy 100%가 "모델 로딩 문제"로만 설명되던 것을 "Fine-tuning 전 초기 상태(정상)" 케이스 추가
- **확장행 단일 열림**: 인라인 평가 테이블에서 행 클릭 시 기존 열린 행은 자동 접힘 (한 번에 하나만 열림)
- **인라인 평가 InfoBadge 설명 추가**: 키워드 비교 기능 안내 + Fine-tuning 효과 설명 2줄 추가

### feat: MLOps 대시보드 — InfoBadge 툴팁 + 키워드 비교 확장행
- **InfoBadge 툴팁 (`?` 아이콘)**: MLOps 대시보드 10개 섹션(파이프라인, 학습 데이터, 품질 추이, 엔터티 오류, 모델 성능, 추출 방식, 배포 인사이트, 인라인 평가, 설정 3종)에 hover 시 설명 툴팁 표시 (`InfoBadge.tsx` 신규)
- **키워드 비교 확장행**: 인라인 평가 활동 테이블에서 행 클릭 시 "현재 모델 추출 vs GPT-5 교정" 엔터티 비교 표시, 엔터티 유형별 색상 코딩 (PS/OG/LC/DT/TI/QT)
- **`original_entities` 컬럼 추가**: `ner_training_samples` 테이블에 평가 시점 원본 추출 엔터티 저장 (Alembic 008)
- **수정 파일**: `MLOpsPage.tsx`, `admin.py`, `ner_training.py`, `ner_training_pipeline.py`, `tasks.py`
- **신규 파일**: `InfoBadge.tsx`, `008_add_original_entities.py`

### fix: 타임라인 기원 기사 정렬 — 백엔드 쿼리 수정
- **문제**: 동일 날짜 기사가 많을 때 기원(origin) 기사가 타임라인 중간에 위치
- **수정**: `timeline.py` 쿼리에 `TimelineEntry.is_origin.desc()` 1차 정렬 추가하여 기원 기사가 항상 첫 번째에 위치
- **수정 파일**: `backend/app/api/routes/timeline.py`

### fix: 6건 버그 수정 및 UX 개선
- **추출 방식 0/0 비율 버그**: BERT NER 0건/kiwipiepy 0건일 때 kiwipiepy가 100%로 표시되던 버그 수정 (`MLOpsPage.tsx`)
- **대시보드 로그 KST 시간**: 로그 뷰어 타임스탬프를 UTC ISO → KST (`MM/DD HH:MM:SS KST`) 형식으로 변경 (`admin.py`)
- **트렌드 카테고리 차트 이중 렌더링**: 탭 진입 시 `loadArticleTrends()` 중복 호출 방지, 기존 데이터가 있으면 재사용 (`TrendsPage.tsx`)
- **타임라인 기원 기사 정렬**: 기사 목록 + 타임라인 차트에서 기원(origin) 기사가 정렬과 무관하게 항상 맨 위에 위치하도록 수정 (`ArticleList.tsx`, `TimelineChart.tsx`)
- **전파 트리 미니맵 제거 + 기원 포커스**: 흰색으로 렌더되던 MiniMap 삭제, 초기 뷰를 기원 노드 중심으로 배율 조정 (`PropagationGraph.tsx`)
- **홈→트렌드 토픽 연동**: 홈에서 실시간 트렌드 토픽 클릭 시 트렌드 탭에서 해당 토픽이 선택+스크롤 이동되도록 구현 (`TrendsPage.tsx`, `HomePage.tsx`)
- **period/data 정합성**: URL period 파라미터 변경 시 캐시된 데이터 무효화하여 불일치 방지

### fix: NER MLOps 파이프라인 — 학습 데이터 수집 정상화
- **GPT-5 function calling JSON 추출 개선**: reasoning 모델이 tool_calls 대신 텍스트로 응답할 때 코드블록/전체 JSON/내장 JSON 3단계 추출 (`azure_openai.py`)
- **tool_choice 호환성**: GPT-5 reasoning 모델과 호환되도록 `tool_choice`를 forced function → `"auto"`로 변경, 프롬프트에 JSON 폴백 형식 안내 (`ner_evaluation_agent.py`)
- **이중 GPT-5 호출 제거**: `save_evaluation_results`에서 `evaluate_and_correct()` 재호출 삭제, `evaluate_batch_sample` 결과의 `corrected_entities` 직접 재사용 (`ner_training_pipeline.py`)
- **과도한 품질 게이트 제거**: 초기 평가 점수 0.7 미만 필터가 모든 샘플을 차단하던 문제 수정 (평가 실패만 스킵)
- **async event loop 충돌 수정**: Celery async task 내에서 `asyncio.new_event_loop()` 호출 시 "Cannot run the event loop while another loop is running" 에러 → `save_evaluation_results`를 async로 전환 (`ner_training_pipeline.py`, `tasks.py`)
- **결과**: 매 크롤링 배치(30분)마다 5건씩 학습 데이터 정상 축적 (0건 → 6건 확인)

---

## 2026-02-20

### feat: MLOps 품질 분석 대시보드 + 배포 시 자동 인사이트
- **품질 추이 차트**: 최근 30일 일별 NER 평균 품질 점수 + 평가 건수 혼합 차트 (ECharts Line+Bar)
- **엔터티 유형별 오류 분포**: GPT-5 교정 엔터티의 type별 도넛 차트 (PS/OG/LC/DT/TI/QT)
- **모델 성능 비교**: 모델 버전별 F1 점수 바 차트, 활성 모델 강조
- **추출 방식 비율**: BERT NER vs kiwipiepy 비율 프로그레스 바
- **배포 인사이트**: 모델 승격 시 GPT-5가 축적 데이터(품질 추이, 엔터티 오류, 모델 히스토리, 평가 사유)를 분석하여 인사이트 자동 생성 → DB 저장 → 대시보드 표시
- **DB 변경**: `ner_model_versions.deployment_insight` 컬럼 추가 (Alembic 007)
- **신규 파일**: `mlops_insight.py` (GPT-5 인사이트 생성 서비스)
- **수정 파일**: `admin.py` (v0.5.0), `ner_training.py`, `finetune_bert_ner.py`, `MLOpsPage.tsx`, `admin-dashboard.spec.ts`

### fix: 트렌드 탭 UX 개선 — 상태 초기화, 비교 상태바, 이중 로딩 방지
- **탭 진입 시 상태 초기화**: 트렌드 탭을 나갔다가 다시 들어올 때 `trendView`, `period`, `expandedClusterId`를 기본값으로 리셋 (Zustand `resetView()` 추가)
- **비교 로딩 상태바**: '비교' 탭 클릭 시 period 전환과 동일한 상단 프로그레스 바 표시 (`isLoadingComparison` 조건 추가)
- **카테고리 분포 이중 로딩 방지**: 마운트 시 2개 `useEffect`(데이터 로딩 + URL period 동기화)를 1개로 통합하여 `loadArticleTrends()` 1회만 호출
- **`loadComparison` 의존성 수정**: `handleSetTrendView`, `handleSetPeriod`의 dependency array에 `loadComparison` 추가하여 stale closure 방지
- **수정 파일**: `TrendsPage.tsx`, `useTrendStore.ts`

### feat: MLOps 대시보드 고도화 — 인라인 평가, KST 예상 시간, 자동 Fine-tuning, 예측 대시보드
- **인라인 평가 활동 카드**: 크롤링 배치마다 실행되는 GPT-5 NER 평가 결과를 최근 24시간 테이블로 시각화 (품질 점수, 추출 방식, 수집 시각)
- **KST 예상 실행 시간**: 모든 MLOps 스케줄 항목에 한국시간(UTC+9) 다음 실행 시각 표시, `_next_cron_run()` 유틸로 crontab 패턴에서 KST 변환
- **자동 Fine-tuning**: `check_training_readiness` 태스크에서 학습 데이터 임계치 도달 시 `trigger_bert_finetune.delay()` 자동 호출 (24시간 내 중복 방지)
- **예측 대시보드**: 현재 단계(데이터 수집 중/fine-tuning 대기), 일일 수집률, 예상 준비 완료일, 다음 자동 트리거 조건을 배너로 표시
- **수정 파일**: `admin.py` (v0.4.0), `tasks.py`, `MLOpsPage.tsx`

### feat: 관리자 대시보드 — 피드 출처 + MLOps 스케줄링 시각화
- **수집 관리 페이지**: 카테고리 RSS 피드 7개 + 언론사 RSS 피드 6개 출처 카드 추가 (URL, 피드당 수집 한도 표시)
- **MLOps 페이지**: 6단계 파이프라인 시각화 (수집 → 평가 → 준비 → 학습 → 배포 → 재추출)
  - 단계별 상태 뱃지 (진행중/완료/대기/수집중), 프로그레스 바, 예상 소요일
  - 학습 데이터 진행률 요약 바 (unused/target)
- **MLOps 스케줄 테이블**: 5개 작업의 주기 및 상세 정보 표시
- **백엔드**: `/api/admin/crawl`에 `feed_sources`, `/api/admin/mlops`에 `schedule`+`pipeline` 필드 추가
- **수정 파일**: `admin.py`, `CollectionPage.tsx`, `MLOpsPage.tsx`

### fix: 관리자 대시보드 데이터 누락 및 undefined 수정
- **JSONB GROUP BY 오류 수정**: `Article.metadata_["category"]` JSONB 컬럼의 GROUP BY에서 parameterized query 불일치로 PostgreSQL 에러 발생 → `literal_column` 사용으로 해결
  - `/api/admin/crawl`: category_stats, publisher_stats, recent_articles, daily_counts 모두 빈 배열 반환 → 정상 데이터 반환
  - `/api/admin/stats`: articles_by_category, top_publishers 빈 배열 반환 → 정상 데이터 반환
- **쿼리 독립 실행**: `/crawl`, `/stats` 엔드포인트의 단일 try/except 블록을 각 쿼리별로 분리하여 한 쿼리 실패 시 다른 데이터까지 빈 값이 되는 연쇄 장애 방지
- **크롤링 상태 필드명 수정**: `crawl.last_run`이 항상 null — `cs.get("updated_at")` → `cs.get("started_at")` (캐시 실제 필드명과 일치)
- **설정 페이지 undefined 수정** (백엔드 + 프론트엔드):
  - `crawling.max_articles_per_run`: 누락 → `MAX_ARTICLES_PER_RUN` (90) 추가
  - `crawling.retention_days`: `system` 섹션에만 있던 값을 `crawling`에도 추가
  - `mlops.max_versions`: `max_model_versions` → `max_versions`로 필드명 통일
  - `system.debug`: 백엔드에 없는 필드 → `system.retention_days` 표시로 대체
  - 프론트엔드 `SettingsData` 인터페이스를 백엔드 실제 응답과 정합성 일치

### feat: 관리자 대시보드 (`/admin`)
- **목적**: 수집현황, MLOps, 시스템 자원, 통계, 로그, 설정을 한눈에 모니터링하는 관리자 콘솔
- **인증**: JWT 기반 단일 관리자 계정 (`.env`에서 `ADMIN_USERNAME`, `ADMIN_PASSWORD` 관리)
- **백엔드**: `/api/admin/*` 9개 엔드포인트 (login, verify, overview, crawl, mlops, system, stats, logs, settings)
  - 인메모리 로그 링 버퍼 (최근 1000건), Celery inspect 연동, psutil 시스템 모니터링
- **프론트엔드**: React 7개 페이지 + 사이드바 레이아웃 + 로그인 페이지
  - 코드 스플릿: 각 페이지 5-10KB gzip
  - 다크/라이트 모드 전환, 30초 자동 새로고침
- **읽기 전용**: 설정 변경 기능 없음 (모니터링 전용)
- **신규 파일**: `auth.py`, `routes/admin.py`, `adminApi.ts`, `useAdminStore.ts`, 9개 페이지 컴포넌트
- **수정 파일**: `config.py`, `requirements.txt`, `main.py`, `App.tsx`, `docker-compose.prod.yml`, `.env.example`

### feat: NER 키워드 추출 품질 개선 MLOps 파이프라인
- **목적**: BERT NER 모델("윤석열" → "윤석"만 추출 등) 품질을 GPT-5 평가 데이터로 점진 개선하는 폐쇄 루프 구축
- **Phase 1 — 학습 데이터 수집**:
  - GPT-5 function calling 기반 NER 평가 에이전트 (`ner_evaluation_agent.py`) — 파싱 실패 제거
  - BIO 태그 변환 + DB 영속화 파이프라인 (`ner_training_pipeline.py`)
  - 크롤링 배치 완료 시 평가 결과 자동 DB 저장 (기존 로그만 기록 → DB 축적)
  - 6시간 주기 추가 학습 데이터 수집 태스크 (`collect_ner_training_data`)
- **Phase 2 — Fine-tuning + 배포**:
  - HuggingFace Trainer 기반 fine-tuning 스크립트 (`scripts/finetune_bert_ner.py`, CPU, epochs=3)
  - 별도 Docker 컨테이너 (`docker compose --profile finetune run finetune`)
  - 모델 버전 관리자 (`model_manager.py`) — 심볼릭 링크 전환, quality gate, 롤백
  - 모델 교체 후 최근 7일 기사 키워드 재추출 태스크 (`reextract_keywords_batch`)
- **DB 스키마**: `ner_training_samples`, `ner_model_versions` 테이블 추가 (Alembic 006)
- **설정**: `config.py`에 MLOps 관련 6개 설정 추가
- **기존 기능 영향 없음**: 서비스 중단 없이 운영, fine-tuning은 별도 컨테이너
- **수정 파일**: 6개 신규 + 8개 수정 (상세는 CLAUDE.md 참조)

---

## 2026-02-19

### fix: 트렌드 페이지 UX 개선 + 현황 패널 용어 변경
- 트렌드 period 전환 시 기존 콘텐츠 유지 + 프로그레스 바 표시 (깜빡임 제거)
- 언론사 필터 ↔ 카테고리 필터 위치 교환, 언론사 필터와 period 셀렉터 수평 정렬
- 현황 패널: '크롤링' → '수집상태', '총 추적' 삭제, '마지막 크롤링' → '마지막 업데이트'

### fix: SSE 연결 상태 표시 개선 — 짧은 끊김 무시
- **문제**: SSE 잠깐 끊길 때마다 "연결 끊김"이 표시되어 사용자 신뢰도 저하
- **수정**: 5초 이상 끊겨 있을 때만 'offline' 상태 표시, 빠른 재연결 시 사용자에게 노출하지 않음 (`Header.tsx`)

### fix: 트렌드 카드 last_seen 시간 표시 오류 + 색상 바 높이
- **문제 1**: `last_seen`이 `published_at`(RSS 발행일, 시간 없이 00:00:00Z)을 사용하여 모든 카드가 동일한 "N시간 전"으로 표시됨
- **수정**: `last_seen`을 `created_at`(실제 수집 시각) 기준으로 변경 (`trend_clustering.py`)
- **문제 2**: 홈 트렌드 카드가 3열 그리드에서 높이가 다를 때 왼쪽 카테고리 색상 바가 카드 전체 높이를 채우지 못함
- **수정**: `CardContent`에 `h-full` 추가 (`HomePage.tsx`)

### fix: 누락된 ORM 모델 파일 추가 + .gitignore 수정
- **문제**: `.gitignore`의 `models/` 규칙(ML 모델 캐시용)이 `backend/app/models/` 디렉토리까지 무시하여 `base.py`, `article.py`, `search_log.py`, `__init__.py` 4개 파일이 git에 커밋되지 않았음
- **수정**: `models/` → `*.bin`, `*.pt`, `*.onnx`, `*.safetensors` 확장자 기반으로 변경
- 모델 파일 4개 커밋 추가

### infra: 호스트 마이그레이션 완료 (i3-2310M → i7-9750H)
- 기존 호스트(Intel i3-2310M, 3.8GB RAM)에서 신규 호스트(Intel i7-9750H, 16GB RAM)로 이전
- PostgreSQL 4325 articles, Qdrant 4766 vectors 복원 완료
- CLAUDE.md 호스트 사양 및 실사용 메모리 수치 업데이트

---

## 2026-02-18

### fix: 클러스터 키워드에서 언론사명 제외 — 품질 개선
- **문제**: Google News RSS 제목에 포함된 언론사명(" - 매일경제" 등)이 NER 키워드로 추출되어 클러스터 사유에 "매일경제" 같은 무의미한 키워드가 표시됨
- **수정 파일**:
  - `backend/app/core/trend_clustering.py`: 클러스터링 시 언론사명 자동 수집(`_collect_publisher_names`) → 키워드 매칭/사유 생성에서 제외(`_filter_keywords_data`)
  - `backend/app/services/keyword_extractor.py`: NER 추출 전 제목에서 언론사 접미사 제거(`_strip_publisher_suffix`)
- 기존 DB 기사(언론사명 포함 키워드)와 신규 기사(제거됨) 모두 대응

### fix: Zod 스키마에 cluster_reason 필드 추가 — 뱃지 미표시 수정
- **문제**: `ClusterArticleSchema`에 `cluster_reason` 필드가 없어 Zod `safeParse()`가 해당 필드를 strip → 프론트엔드에서 뱃지 미표시
- **수정 파일**: `frontend/src/lib/schemas.ts`
- `cluster_reason: z.string().nullable().optional()` 추가

### feat: 클러스터 기사 목록 UI 개선 — 대표 뱃지 + 공통점 인라인
- **수정 파일**: `frontend/src/pages/TrendsPage.tsx`
- 대표 기사에 "대표" 뱃지, 사용자 선택 기사에 "선택" 뱃지 표시
- `cluster_reason` 인라인 표시 (공통 키워드/유사도 사유)
- 트렌드 페이지 이탈 시 선택 상태 초기화 (`useTrendStore.resetSelectedArticle`)

### feat: 전파트리 React Flow 마이그레이션 + 카드형 디자인
- **변경**: `@antv/g6` → `@xyflow/react` (React Flow v12) + `@dagrejs/dagre` 전환
- **수정 파일**: `frontend/src/components/visualization/PropagationGraph.tsx` (전면 재작성)
- dagre LR 레이아웃 + serpentine 행 줄바꿈 (MAX_COLS_PER_ROW=4)
- 커스텀 카드형 노드: 흰색 배경 + 좌측 라이프사이클 컬러바 + 그림자
- 제목 2줄 허용 (truncate 50자), 유사도 배지, 라이프사이클 라벨 표시
- fitView (maxZoom 0.8) + panOnScroll + 확대/축소 지원
- MiniMap/Controls 제거 (사용자 피드백 반영)
- 번들 사이즈 83% 감소 (vendor-g6 1,353KB → PropagationGraph 229KB)

### feat: 전파트리 모달 풀사이즈
- **수정 파일**: `frontend/src/pages/TimelinePage.tsx`
- 모달 `sm:h-[95vh] sm:w-[97vw]` (max-w/max-h 제한 제거)

### fix: 트렌드 기간 전환 504 타임아웃 — 캐시 워밍 도입
- **문제**: 7d/30d 트렌드 클러스터링이 최대 48초 소요 → nginx 60s timeout → 504
- **근본 원인**: 크롤링 후 캐시 삭제만 하고 재계산하지 않아 다음 사용자 요청 시 on-demand 계산
- **수정 파일**: `backend/app/workers/tasks.py`
  - 크롤링 완료 후 24h/7d/30d 트렌드 캐시 미리 계산하여 Redis 저장 (TTL 1시간)
  - 사용자 요청 시 항상 캐시 히트 (<10ms)
- **안전장치**: `docker/nginx/nginx.prod.conf` proxy_read_timeout 60s→180s, `frontend/src/services/api.ts` axios timeout 30s→120s

### fix: Celery 크롤링 16시간 중단 — stale Redis lock 수정
- **문제**: `fetch_trending_news` 태스크가 매 실행 시 `already_running`으로 skip
- **원인**: Celery 태스크마다 새 이벤트 루프를 생성하는데, 이전 루프의 Redis 클라이언트(`_redis` 전역변수)가 stale 상태로 남아 `_exec_redis` 재연결 시 `SET NX`가 실패
- **추가 버그**: `finally` 블록에서 락을 획득하지 않은 태스크도 무조건 `release_task_lock` 호출
- **수정 파일**: `backend/app/workers/tasks.py`
  - 태스크 시작 시 `_reset_redis()` 호출하여 stale 연결 선제 제거
  - `lock_acquired = False` 안전한 기본값
  - `if lock_acquired:` 조건으로 락을 획득한 경우에만 해제

### feat: 로고 클릭 시 data refresh
- **수정 파일**: `frontend/src/components/layout/Header.tsx`
- 로고 클릭 시 `loadStats`, `loadCrawlStatus`, `loadArticleTrends`, `loadRecentArticles` 호출

### feat: 홈 실시간 트렌드 카테고리별 1개 + UX 개선
- **수정 파일**: `frontend/src/pages/HomePage.tsx`
- 카테고리별 대표 1개 클러스터만 표시 (기존 상위 9개 → 카테고리별 필터)
- 카드 좌측 카테고리 색상 바, 제목 크기 확대, 대표 언론사 표시

### fix: 트렌드 페이지 period 필터 즉시 반영
- **수정 파일**: `frontend/src/stores/useTrendStore.ts`
- `setPeriod`에서 기존 데이터 클리어 + `isLoading=true` 강제 설정
- 기존: 이전 period 데이터가 남아 변화 체감 불가 → 수정: skeleton UI 표시 후 새 데이터 렌더링

### docs: CLAUDE.md 구조화 + 하위 문서 분리
- CLAUDE.md에 Deployment, Documentation Rules, Linked Documents 섹션 추가
- `docs/deployment.md` 신규 (배포 가이드)
- `docs/changelog.md` 신규 (변경 이력)
