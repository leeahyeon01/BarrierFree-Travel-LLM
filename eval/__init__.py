"""
RAG 평가 파이프라인 패키지

모듈:
  retrieval_eval  - Precision@k / Recall@k / MRR
  faithfulness_eval - GPT 기반 충실도 평가
  coverage_eval   - 요구사항 반영도 평가
  rule_eval       - 규칙 기반 검사 (세션 수·시간·그룹 구성)
  run_eval        - 통합 실행 스크립트
"""

from .retrieval_eval import evaluate_retrieval
from .faithfulness_eval import evaluate_faithfulness
from .coverage_eval import evaluate_coverage
from .rule_eval import evaluate_rules

__all__ = [
    "evaluate_retrieval",
    "evaluate_faithfulness",
    "evaluate_coverage",
    "evaluate_rules",
]
