# RAG 평가 리포트

생성일시: 2026-04-28 13:36  |  총 케이스: 5건

## 요약 점수

| 지표 | 점수 |
|------|------|
| Precision@k | 0.400 ❌ |
| Recall@k    | 1.000 ✅ |
| MRR         | 0.900 ✅ |
| Faithfulness | 0.000 ❌ |
| Coverage    | 1.000 ✅ |
| Rules (평균) | 0.667 ⚠️ |
| Rules (통과율) | 0.333 ❌ |

## 케이스별 결과

### [TC-001] 경복궁 휠체어 접근성
- **Retrieval** P@5=0.400  R@5=1.000  MRR=1.000
- **Faithfulness** 0.000  (S=0 C=0 NF=0)
- **Coverage** 1.000  미커버: 없음
- **Rules** session_count=✅  daily_time=✅  group_composition=✅

### [TC-002] 서울 무장애 2박 3일 여행 일정
- **Retrieval** P@5=0.600  R@5=1.000  MRR=1.000
- **Faithfulness** 0.000  (S=0 C=0 NF=0)
- **Coverage** 1.000  미커버: 없음
- **Rules** session_count=❌  daily_time=❌  group_composition=✅

### [TC-003] 부산 장애인 콜택시 이용 방법
- **Retrieval** P@5=0.200  R@5=1.000  MRR=1.000
- **Faithfulness** 0.000  (S=0 C=0 NF=0)
- **Coverage** 1.000  미커버: 없음

### [TC-004] 제주 휠체어 해변 접근 가능한 곳
- **Retrieval** P@5=0.400  R@5=1.000  MRR=0.500
- **Faithfulness** 0.000  (S=0 C=0 NF=0)
- **Coverage** 1.000  미커버: 없음

### [TC-005] 고령자·유아 동반 가족 무장애 여행 추천
- **Retrieval** P@5=0.400  R@5=1.000  MRR=1.000
- **Faithfulness** 0.000  (S=0 C=0 NF=0)
- **Coverage** 1.000  미커버: 없음
- **Rules** session_count=❌  daily_time=✅  group_composition=✅
