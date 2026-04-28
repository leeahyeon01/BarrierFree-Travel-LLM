"""
Requirement Coverage(요구사항 반영도) 평가 모듈
- 테스트케이스에 정의된 필수 항목이 답변에 언급되었는지 확인
- 키워드 기반(빠르고 무료) + 선택적 GPT 기반(정확도 높음) 두 모드 지원
"""

from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, field

from openai import OpenAI

_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

_GPT_PROMPT = """\
아래 [답변]이 [요구사항] 항목들을 각각 다루고 있는지 평가하세요.
각 항목에 대해 covered(언급됨) 또는 missing(미언급)을 판단하세요.
결과는 JSON:
{{
  "results": [
    {{"requirement": "항목명", "covered": true/false, "evidence": "근거 문장 또는 빈 문자열"}},
    ...
  ]
}}

[요구사항]
{requirements}

[답변]
{answer}
"""


@dataclass
class CoverageResult:
    score: float                           # 0~1 (커버된 항목 비율)
    num_requirements: int
    covered: int
    missing: int
    details: list[dict] = field(default_factory=list)
    mode: str = "keyword"


def _keyword_check(answer: str, requirement: str) -> bool:
    """요구사항 문자열의 핵심 키워드가 답변에 포함되는지 간단 확인"""
    # 조사·조동사 등 불필요한 어미 제거 후 2글자 이상 단어 추출
    tokens = re.findall(r"[가-힣a-zA-Z0-9]{2,}", requirement)
    if not tokens:
        return False
    answer_lower = answer.lower()
    return any(tok.lower() in answer_lower for tok in tokens)


def evaluate_coverage(
    answer: str,
    requirements: list[str],
    mode: str = "keyword",
) -> CoverageResult:
    """
    답변이 요구사항 목록을 얼마나 반영했는지 평가.

    Args:
        answer:       RAG 시스템이 생성한 답변
        requirements: 필수 언급 항목 목록
                      예: ["휠체어 접근 가능 여부", "주차 정보", "엘리베이터 유무"]
        mode:         "keyword" (빠름, 무료) | "gpt" (정확, 유료)

    Returns:
        CoverageResult
    """
    if not requirements:
        return CoverageResult(score=1.0, num_requirements=0, covered=0, missing=0, mode=mode)

    if mode == "gpt":
        return _gpt_coverage(answer, requirements)

    # keyword 모드
    details = []
    for req in requirements:
        covered = _keyword_check(answer, req)
        details.append({"requirement": req, "covered": covered, "evidence": ""})

    covered_count = sum(1 for d in details if d["covered"])
    return CoverageResult(
        score=covered_count / len(requirements),
        num_requirements=len(requirements),
        covered=covered_count,
        missing=len(requirements) - covered_count,
        details=details,
        mode="keyword",
    )


def _gpt_coverage(answer: str, requirements: list[str]) -> CoverageResult:
    req_text = "\n".join(f"- {r}" for r in requirements)
    prompt = _GPT_PROMPT.format(requirements=req_text, answer=answer[:3000])
    try:
        resp = _openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        results = data.get("results", [])
        covered_count = sum(1 for r in results if r.get("covered"))
        return CoverageResult(
            score=covered_count / len(requirements),
            num_requirements=len(requirements),
            covered=covered_count,
            missing=len(requirements) - covered_count,
            details=results,
            mode="gpt",
        )
    except Exception as e:
        # GPT 실패 시 keyword fallback
        fallback = evaluate_coverage(answer, requirements, mode="keyword")
        fallback.mode = f"keyword(gpt_fallback: {e})"
        return fallback
