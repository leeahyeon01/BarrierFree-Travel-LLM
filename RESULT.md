# 배리어프리 여행 플래너 — 프로젝트 산출물

---

## 1. 문제정의

### 배경

국내 교통약자(휠체어 이용자, 노인, 영유아 동반 가족 등)는 여행 계획 시 접근성 정보를 얻기 위해 수십 개의 공공 데이터 포털, 관광지 공식 홈페이지, 블로그 후기를 직접 확인해야 한다. 한국관광공사 API는 관광지 기본 정보를 제공하지만 접근성 필드는 대부분 비어 있거나 부정확하다.

### 핵심 문제

| 문제 | 설명 |
|------|------|
| **정보 분산** | 접근성 정보가 공공 API, 블로그, SNS, 지자체 홈페이지 등에 분산 |
| **최신성 부족** | 공공 데이터의 접근성 항목은 수년간 갱신되지 않는 경우 다수 |
| **개인화 부재** | 휠체어 사용자, 시각장애인, 유모차 동반 등 요구사항이 다름에도 일괄 제공 |
| **일정 통합 불가** | 접근성 정보와 여행 일정 생성이 분리되어 수동 조합 필요 |
| **신뢰성 검증 불가** | 제공된 정보가 실제 방문 시 맞는지 사전 확인 수단 없음 |

### 목표

교통약자가 자연어로 여행 조건을 입력하면 → 접근성 검증이 완료된 장소만으로 구성된 맞춤 일정을 자동 생성하는 AI 시스템 구축

---

## 2. 해결방안

### 접근 전략

**RAG(Retrieval-Augmented Generation) + MultiAgent 파이프라인**을 결합하여 최신 접근성 정보 기반의 신뢰 가능한 일정을 생성한다.

#### 2-1. 데이터 수집 및 인덱싱

- **한국관광공사 KorWithService2 API**: 전국 17개 시도 × 5개 카테고리(관광지·문화시설·축제·숙박·음식점) 크롤링
- **Naver 블로그/뉴스/지식인**: 각 장소별 최신 실사용자 후기에서 접근성 사실 추출
- **서울 열린데이터광장**: 저상버스 노선, 지하철 엘리베이터 위치
- **전국 17개 도시 장애인 콜택시 DB**: 정적 데이터베이스로 내장
- **Kakao Local/Mobility API**: 주변 교통수단, 경로 정보

수집된 데이터는 GPT로 문서 수준 맥락을 생성(Contextual Embedding) 후 Qdrant 벡터 DB에 5개 컬렉션으로 저장한다.

#### 2-2. MultiAgent 구조

| 에이전트 | 역할 |
|----------|------|
| `IntentAgent` | 사용자 메시지 → 구조화된 여행 의도 추출 (목적지, 기간, 접근성 요구사항, 동반 유형) |
| `PlaceSearchAgent` | RAG 검색으로 후보 장소 수집, 이미 제외된 장소 필터링 |
| `ValidationAgent` | Naver 실시간 검색 or LLM fallback으로 각 장소 접근성 실제 검증 |
| `ItineraryAgent` | 검증 통과 장소만으로 GPT-4o 기반 일정 생성 |
| `EvalAgent` | 생성 일정의 품질 평가 (코드 검증 + LLM 평가) |
| `OrchestratorAgent` | 전체 파이프라인 조율, 안전 장소 부족 시 최대 2회 재검색 |

#### 2-3. 실시간 접근성 검증

Naver 블로그/뉴스/지식인 API로 해당 장소의 최신 후기를 수집한 뒤, GPT가 접근성 사실(입구 단차, 휠체어 이용 가능 여부, 장애인 화장실 유무 등)을 추론한다. Naver API 미연결 시 LLM이 장소 메타데이터 기반 fallback 검증을 수행한다.

#### 2-4. 품질 평가

- **코드 검증** (API 비용 없음): 세션 수, 일일 소요 시간 범위, 동반 그룹 키워드 언급
- **LLM 검증** (GPT 호출): Faithfulness(답변이 증거에 근거하는 비율), Coverage(접근성 요구사항 반영 비율)

---

## 3. 트레이드오프

### 3-1. SingleAgent vs MultiAgent

| 항목 | SingleAgent (05) | MultiAgent (06) |
|------|-----------------|-----------------|
| **복잡도** | 낮음 — 단일 ReAct 루프 | 높음 — 에이전트 간 인터페이스 설계 필요 |
| **디버깅** | 어려움 — 실패 지점 특정 곤란 | 쉬움 — 각 에이전트 로그 분리 |
| **재시도 제어** | 불가 — 루프 내 암묵적 처리 | 가능 — Orchestrator가 명시적 재시도 |
| **검증 통합** | 없음 — 스텁 함수로 대체 | 실제 Naver API + LLM fallback |
| **API 비용** | 낮음 (단순 루프) | 높음 (에이전트별 GPT 호출) |
| **확장성** | 낮음 — 새 기능 = 전체 수정 | 높음 — 에이전트 단위 교체 가능 |

**선택 이유**: 접근성 검증이 핵심 기능이므로 검증 실패 재시도, 검증 결과 이력 관리가 필수 → MultiAgent 채택

### 3-2. RAG vs 순수 웹 검색

| 항목 | RAG (Qdrant) | 순수 웹 검색 (Naver/Google) |
|------|-------------|--------------------------|
| **응답 속도** | 빠름 (벡터 검색 < 100ms) | 느림 (HTTP 왕복 + 파싱) |
| **비용** | 초기 인덱싱 비용 | API 호출 횟수 비용 |
| **최신성** | 인덱싱 시점에 종속 | 실시간 |
| **접근성 특화** | Contextual Embedding으로 접근성 문서에 특화 | 일반 검색 노이즈 포함 |

**선택**: RAG로 1차 후보 수집 + Naver 실시간으로 검증 (2단계 하이브리드)

### 3-3. 하이브리드 검색 (Dense + BM25) vs Dense Only

- Dense만 사용 시: "엘리베이터", "경사로" 등 정확한 키워드 검색이 약함
- BM25 추가 시: 정확한 용어 매칭 + 의미 검색 조합으로 재현율 향상
- 단점: 한국어 형태소 분석기 미설치 환경에서 character bigram 방식으로 fallback → 복합어 분리 정밀도 저하

### 3-4. GPT-4o vs GPT-4o-mini

| 에이전트 | 모델 | 이유 |
|----------|------|------|
| IntentAgent | gpt-4o-mini | 구조화 추출 — 고성능 불필요 |
| PlaceSearchAgent | gpt-4o-mini | 목록 필터링 — 단순 |
| ValidationAgent | gpt-4o-mini | 이진 판단 |
| ItineraryAgent | gpt-4o | 창의적 일정 구성, 한국어 품질 |
| EvalAgent (LLM checks) | gpt-4o-mini | 채점 — 정밀도보다 속도 우선 |

### 3-5. JSON 파일 스토리지 vs DB

- 현재: JSON 파일(`data/itineraries/`) — 단일 서버 배포 환경에서 충분, 의존성 최소
- 한계: 다중 인스턴스 배포 시 동시성 문제, 대용량 이력 조회 성능 저하
- 개선 방향: SQLite → PostgreSQL 전환 경로 확보 (CRUD 레이어 분리로 교체 용이)

---

## 4. 시스템 아키텍처

```mermaid
graph TB
    subgraph Client["클라이언트 레이어"]
        UI["Streamlit Frontend\n- 자연어 입력\n- 일정 카드뷰\n- 🔴 위험 장소 배너\n- 일정 다운로드/삭제"]
    end

    subgraph API["API 레이어 (FastAPI)"]
        CHAT["POST /chat"]
        CRUD["GET/DELETE /itineraries"]
        STORE["JSON File Storage\ndata/itineraries/"]
    end

    subgraph Agents["MultiAgent 레이어"]
        ORC["OrchestratorAgent\n재시도 조율 (max 2회)"]
        INT["IntentAgent\ngpt-4o-mini"]
        PSA["PlaceSearchAgent\ngpt-4o-mini"]
        VAL["ValidationAgent\nNaver + LLM fallback"]
        ITA["ItineraryAgent\ngpt-4o"]
        EVA["EvalAgent\n코드검증 + LLM검증"]
    end

    subgraph RAG["RAG 레이어"]
        RET["retrieval.py\n단일 진입점"]
        VS["Qdrant VectorDB\n5개 컬렉션"]
        EMB["OpenAI Embeddings\ntext-embedding-3-small\n1536d"]
        BM25["BM25 Korean Bigram\n하이브리드 검색"]
    end

    subgraph External["외부 API"]
        TOUR["한국관광공사\nKorWithService2"]
        NAVER["Naver Search API\n블로그·뉴스·지식인"]
        KAKAO["Kakao Local/Mobility"]
        SEOUL["서울 열린데이터\n저상버스·지하철 엘리베이터"]
    end

    subgraph Eval["평가 모듈"]
        FAITH["faithfulness_eval\nGPT claim 검증"]
        COV["coverage_eval\n요구사항 반영률"]
        RULE["rule_eval\n규칙 기반 검증"]
    end

    UI -->|"HTTP POST"| CHAT
    UI -->|"HTTP GET/DELETE"| CRUD
    CHAT --> ORC
    CRUD --> STORE

    ORC --> INT
    ORC --> PSA
    ORC --> VAL
    ORC --> ITA
    ORC --> EVA
    ORC --> STORE

    PSA --> RET
    RET --> VS
    RET --> BM25
    VS --> EMB

    VAL -->|"실시간 검증"| NAVER
    VAL -->|"fallback"| INT

    EVA --> FAITH
    EVA --> COV
    EVA --> RULE

    style Client fill:#dbeafe
    style API fill:#dcfce7
    style Agents fill:#fef9c3
    style RAG fill:#fce7f3
    style External fill:#f3e8ff
    style Eval fill:#ffedd5
```

### 컬렉션 구조 (Qdrant)

| 컬렉션 | 내용 | 검색 방식 |
|--------|------|-----------|
| `tour_places` | 관광지·음식점·숙박 기본 정보 | Dense |
| `tour_overview_chunks` | GPT Contextual Chunking 청크 | Dense + BM25 Hybrid |
| `accessibility_chunks` | 접근성 특화 청크 | Dense + BM25 Hybrid |
| `transport_info` | 교통 접근성 정보 | Dense |
| `festival_news` | 축제·행사 정보 (Naver) | Dense |

---

## 5. 파이프라인

### 5-1. 데이터 인덱싱 파이프라인

```mermaid
flowchart TD
    subgraph Ingest["ingest.py — 4단계 수집"]
        A["1단계: 관광지 수집\nKorWithService2 API\n17개 시도 × 5개 카테고리"] --> B["2단계: 축제 정보 수집\nNaver 블로그/뉴스 검색\n지역별 축제·행사"]
        B --> C["3단계: 교통 정보 수집\n- 장애인 콜택시 DB (17개 도시)\n- 서울 저상버스 노선\n- 지하철 엘리베이터\n- Kakao Local API"]
        C --> D["4단계: 텍스트 청킹 + 임베딩\nGPT Contextual Chunk 생성\nOpenAI Embedding 변환"]
    end

    subgraph Storage["저장"]
        E["Qdrant\ntour_places"]
        F["Qdrant\nfestival_news"]
        G["Qdrant\ntransport_info"]
        H["Qdrant\ntour_overview_chunks\naccessibility_chunks"]
    end

    A --> E
    B --> F
    C --> G
    D --> H

    style Ingest fill:#f0fdf4
    style Storage fill:#eff6ff
```

### 5-2. 쿼리·응답 파이프라인

```mermaid
flowchart TD
    U(["사용자\n자연어 입력"]) --> ORC

    subgraph ORC["OrchestratorAgent"]
        direction TB
        O1["IntentAgent\n여행 의도 추출\n목적지·기간·접근성 요구·동반 유형"] --> O2

        subgraph RETRY["재시도 루프 (max 2회)"]
            O2["PlaceSearchAgent\nRAG 검색 + LLM 필터\n이전 제외 장소 건너뜀"] --> O3
            O3["ValidationAgent\nNaver 실시간 검증\n(불가 시 LLM fallback)"] --> O4{{"안전 장소\n≥ 일수 × 2?"}}
            O4 -->|"No → 재시도"| O2
        end

        O4 -->|"Yes"| O5
        O5["ItineraryAgent\ngpt-4o 일정 생성\n✅ 안전 장소만 포함\n🔴 제외 장소 명시"] --> O6
        O6["EvalAgent\n코드 검증: 세션 수·시간·그룹\nLLM 검증: Faithfulness·Coverage"]
    end

    ORC --> R["ChatResponse\n{reply, complete,\nitinerary, validation_result}"]
    R --> SAVE["JSON 파일 저장\ndata/itineraries/"]
    R --> UI["Streamlit UI\n- 일정 카드뷰 렌더링\n- 🔴 경고 배너\n- 다운로드 버튼"]

    subgraph RAG_DETAIL["RAG 내부 (PlaceSearchAgent 호출 시)"]
        direction LR
        Q["검색 쿼리\n+ 동의어 확장"] --> HYB["Hybrid Search\nDense + BM25"]
        HYB --> RRF["RRF 점수 통합"]
        RRF --> DEDUP["이름 중복 제거\n(top_k=15)"]
    end

    O2 -.->|"retrieve_places()"| RAG_DETAIL

    style ORC fill:#fef9c3
    style RETRY fill:#fff7ed,stroke:#f97316,stroke-dasharray: 5 5
    style RAG_DETAIL fill:#fce7f3
```

### 5-3. 평가 파이프라인

```mermaid
flowchart LR
    IT["생성된 Itinerary"] --> CE & LE

    subgraph CE["코드 검증 (API 비용 없음)"]
        C1["session_count_ok\n일별 세션 수 ≥ 1"]
        C2["daily_time_ok\n일별 소요 시간 1~12시간"]
        C3["group_composition_ok\n동반 그룹 키워드 언급"]
    end

    subgraph LE["LLM 검증 (GPT 호출)"]
        L1["Faithfulness\nGPT claim 추출\n→ SUPPORTED / CONTRADICTED\n목표: ≥ 0.7"]
        L2["Coverage\n접근성 요구사항\n반영 비율\n목표: ≥ 0.7"]
    end

    CE --> PASS{{"overall_pass?"}}
    LE --> PASS

    PASS -->|"true"| OK["✅ 검증 통과\n일정 저장"]
    PASS -->|"false"| WARN["⚠️ 검증 미통과\n일정 저장 + 경고 표시"]

    style CE fill:#dcfce7
    style LE fill:#fef9c3
```
