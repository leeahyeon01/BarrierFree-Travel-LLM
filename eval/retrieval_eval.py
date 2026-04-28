"""
Retrieval 평가 모듈
- Precision@k : 상위 k개 중 관련 문서 비율
- Recall@k    : 전체 관련 문서 중 상위 k개에서 찾은 비율
- MRR         : Mean Reciprocal Rank (첫 번째 관련 문서의 역순위 평균)
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class RetrievalResult:
    precision_at_k: float
    recall_at_k: float
    mrr: float
    k: int
    relevant_found: int
    relevant_total: int
    retrieved_ids: list[str] = field(default_factory=list)


def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """상위 k개 검색 결과 중 관련 문서 비율"""
    if k == 0:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / k


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """전체 관련 문서 대비 상위 k개에서 찾은 비율"""
    if not relevant_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / len(relevant_ids)


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """첫 번째 관련 문서의 역순위 (없으면 0)"""
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def evaluate_retrieval(
    retrieved_ids: list[str],
    relevant_ids: list[str],
    k: int = 5,
) -> RetrievalResult:
    """
    단일 쿼리에 대한 검색 평가.

    Args:
        retrieved_ids: 검색 시스템이 반환한 문서 ID 리스트 (순위 순)
        relevant_ids:  정답 관련 문서 ID 리스트
        k:             평가 기준 상위 k개

    Returns:
        RetrievalResult dataclass
    """
    relevant_set = set(relevant_ids)
    top_k = retrieved_ids[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_set)

    return RetrievalResult(
        precision_at_k=precision_at_k(retrieved_ids, relevant_set, k),
        recall_at_k=recall_at_k(retrieved_ids, relevant_set, k),
        mrr=reciprocal_rank(retrieved_ids, relevant_set),
        k=k,
        relevant_found=hits,
        relevant_total=len(relevant_set),
        retrieved_ids=retrieved_ids,
    )


def evaluate_retrieval_batch(
    cases: list[dict],
    k: int = 5,
) -> dict:
    """
    여러 쿼리에 대한 평균 검색 평가.

    cases 항목 형식:
        {
          "query": "경복궁 휠체어 접근성",
          "retrieved_ids": ["doc_1", "doc_3", ...],
          "relevant_ids": ["doc_1", "doc_2", ...]
        }

    Returns:
        {
          "mean_precision_at_k": float,
          "mean_recall_at_k": float,
          "mrr": float,
          "k": int,
          "num_queries": int,
          "per_query": [RetrievalResult, ...]
        }
    """
    results = [
        evaluate_retrieval(c["retrieved_ids"], c["relevant_ids"], k)
        for c in cases
    ]
    n = len(results)
    if n == 0:
        return {"mean_precision_at_k": 0.0, "mean_recall_at_k": 0.0, "mrr": 0.0,
                "k": k, "num_queries": 0, "per_query": []}

    return {
        "mean_precision_at_k": sum(r.precision_at_k for r in results) / n,
        "mean_recall_at_k":    sum(r.recall_at_k    for r in results) / n,
        "mrr":                 sum(r.mrr             for r in results) / n,
        "k": k,
        "num_queries": n,
        "per_query": [vars(r) for r in results],
    }
