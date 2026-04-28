# RAG 평가 파이프라인

무장애 여행 챗봇의 RAG 시스템 품질을 측정하는 평가 모듈 모음입니다.

---

## 디렉토리 구조

```
eval/
├── __init__.py             # 패키지 진입점
├── retrieval_eval.py       # Precision@k / Recall@k / MRR
├── faithfulness_eval.py    # GPT 기반 충실도 평가
├── coverage_eval.py        # 요구사항 반영도 평가
├── rule_eval.py            # 규칙 기반 검사 (세션·시간·그룹)
├── run_eval.py             # 통합 실행 스크립트
├── testset_template.json   # 테스트셋 템플릿
└── README.md
```

---

## 평가 지표

| 모듈 | 지표 | 설명 |
|------|------|------|
| `retrieval_eval` | Precision@k | 상위 k개 중 관련 문서 비율 |
| `retrieval_eval` | Recall@k | 전체 관련 문서 중 상위 k에서 찾은 비율 |
| `retrieval_eval` | MRR | 첫 번째 관련 문서의 역순위 평균 |
| `faithfulness_eval` | Faithfulness | 답변 주장이 컨텍스트에 근거하는 비율 (GPT) |
| `coverage_eval` | Coverage | 필수 요구사항 반영 비율 (키워드 or GPT) |
| `rule_eval` | Rules | 세션 수 / 하루 시간 / 그룹 언급 통과율 |

---

## 사용법

### 1. 테스트셋 준비

`testset_template.json`을 복사해 실제 케이스를 채웁니다.

```json
[
  {
    "id": "TC-001",
    "query": "경복궁 휠체어 접근성",
    "retrieved_ids": ["doc_123", "doc_456"],
    "relevant_ids": ["doc_123"],
    "context_chunks": [{"content": "...", "source": "..."}],
    "generated_answer": "RAG가 생성한 답변",
    "requirements": ["휠체어 접근 가능 여부", "장애인 화장실 유무"],
    "rule_config": {
      "expected_days": 1,
      "sessions_per_day": 1,
      "min_hours": 1,
      "max_hours": 6,
      "required_groups": ["wheelchair"]
    }
  }
]
```

> `rule_config`가 `null`이면 Rule 검사를 건너뜁니다.  
> `relevant_ids`/`retrieved_ids`가 없으면 Retrieval 평가를 건너뜁니다.

### 2. 평가 실행

```bash
# 기본 실행 (keyword coverage, Faithfulness 포함)
python eval/run_eval.py --testset eval/testset_template.json

# Faithfulness 건너뜀 (API 비용 절약)
python eval/run_eval.py --testset eval/testset_template.json --skip-faithfulness

# GPT 기반 Coverage 평가
python eval/run_eval.py --testset eval/testset_template.json --coverage gpt

# 출력 경로 지정
python eval/run_eval.py \
  --testset eval/my_testset.json \
  --k 5 \
  --out-json reports/result.json \
  --out-md reports/result.md
```

### 3. 결과 확인

평가 완료 후 두 파일이 생성됩니다.

- **`eval_report.json`** — 기계 처리용 전체 결과 (요약 + 케이스별 상세)
- **`eval_report.md`** — 사람이 읽기 편한 Markdown 리포트

콘솔에도 요약 점수가 출력됩니다.

```
==================================================
  평가 요약
==================================================
  Precision@5  : 0.6
  Recall@5     : 0.75
  MRR          : 0.8333
  Faithfulness : 0.857
  Coverage     : 0.9
  Rules 통과율  : 1.0
==================================================
```

---

## 모듈 단독 사용

각 모듈은 독립적으로 import해서 사용할 수 있습니다.

```python
from eval.retrieval_eval import evaluate_retrieval
from eval.faithfulness_eval import evaluate_faithfulness
from eval.coverage_eval import evaluate_coverage
from eval.rule_eval import evaluate_rules

# Retrieval
result = evaluate_retrieval(
    retrieved_ids=["doc_1", "doc_3", "doc_5"],
    relevant_ids=["doc_1", "doc_5"],
    k=5,
)
print(result.precision_at_k)  # 0.4

# Faithfulness
result = evaluate_faithfulness(
    answer="경복궁은 무료 휠체어 대여 서비스를 제공합니다.",
    context_chunks=["경복궁은 휠체어 대여 서비스를 무료로 제공합니다."],
)
print(result.score)  # 1.0

# Coverage
result = evaluate_coverage(
    answer="경복궁은 휠체어 접근이 가능하고 장애인 주차장이 있습니다.",
    requirements=["휠체어 접근 가능 여부", "주차 정보", "엘리베이터 유무"],
)
print(result.score)  # 0.667

# Rules
result = evaluate_rules(
    answer="오전: A 방문 (2시간)\n오후: B 방문 (3시간)\n저녁: C 방문 (1시간)",
    expected_days=1,
    sessions_per_day=3,
    required_groups=["wheelchair"],
)
print(result.passed)
```

---

## 테스트셋 필드 설명

| 필드 | 필수 | 설명 |
|------|------|------|
| `id` | ✅ | 케이스 식별자 |
| `query` | ✅ | 검색 쿼리 |
| `retrieved_ids` | — | 검색 시스템이 반환한 문서 ID 목록 |
| `relevant_ids` | — | 정답 관련 문서 ID 목록 |
| `context_chunks` | — | 검색된 청크 목록 (`{"content": ...}` or 문자열) |
| `generated_answer` | — | RAG가 생성한 답변 |
| `expected_answer` | — | 기대 답변 (없으면 generated_answer 사용) |
| `requirements` | — | Coverage 평가용 필수 항목 목록 |
| `rule_config` | — | Rule 평가 설정 (null이면 건너뜀) |

`rule_config` 하위 필드:

| 필드 | 기본값 | 설명 |
|------|--------|------|
| `expected_days` | 1 | 여행 일수 |
| `sessions_per_day` | 3 | 하루 세션 수 |
| `min_hours` | 4.0 | 하루 최소 소요시간 (h) |
| `max_hours` | 10.0 | 하루 최대 소요시간 (h) |
| `required_groups` | [] | 필수 그룹: `wheelchair` / `elderly` / `infant` |
