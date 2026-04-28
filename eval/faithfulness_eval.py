"""
Faithfulness(충실도) 평가 모듈
- 생성된 답변의 각 주장(claim)이 검색된 컨텍스트에 근거하는지 GPT로 평가
- 점수 = 컨텍스트 기반 claim 수 / 전체 claim 수
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, field

from openai import OpenAI

_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

_EXTRACT_PROMPT = """\
아래 [답변]에서 사실 주장(factual claim)을 추출하세요.
주장은 검증 가능한 명제여야 합니다 (예: "입구에 단차가 없다", "엘리베이터가 있다").
결과는 JSON: {"claims": ["주장1", "주장2", ...]}

[답변]
{answer}
"""

_VERIFY_PROMPT = """\
아래 [컨텍스트]를 근거로 [주장]이 지지되는지(SUPPORTED), 부정되는지(CONTRADICTED),
컨텍스트에 정보가 없는지(NOT_FOUND) 판단하세요.
결과는 JSON: {{"verdict": "SUPPORTED"|"CONTRADICTED"|"NOT_FOUND", "evidence": "근거 문장"}}

[컨텍스트]
{context}

[주장]
{claim}
"""


@dataclass
class FaithfulnessResult:
    score: float                          # 0~1 (SUPPORTED 비율)
    num_claims: int
    supported: int
    contradicted: int
    not_found: int
    claim_verdicts: list[dict] = field(default_factory=list)
    error: str = ""


def _extract_claims(answer: str) -> list[str]:
    prompt = _EXTRACT_PROMPT.format(answer=answer)
    resp = _openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=512,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    return data.get("claims", [])


def _verify_claim(claim: str, context: str) -> dict:
    prompt = _VERIFY_PROMPT.format(context=context[:3000], claim=claim)
    resp = _openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=200,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    return {
        "claim": claim,
        "verdict": data.get("verdict", "NOT_FOUND"),
        "evidence": data.get("evidence", ""),
    }


def evaluate_faithfulness(
    answer: str,
    context_chunks: list[str | dict],
) -> FaithfulnessResult:
    """
    생성된 답변이 검색 컨텍스트에 얼마나 충실한지 평가.

    Args:
        answer:         RAG 시스템이 생성한 답변 텍스트
        context_chunks: 검색된 문서 목록. str 또는 {"content": ..., "text": ...} dict

    Returns:
        FaithfulnessResult
    """
    # 컨텍스트 텍스트 통합
    texts = []
    for chunk in context_chunks:
        if isinstance(chunk, str):
            texts.append(chunk)
        elif isinstance(chunk, dict):
            texts.append(chunk.get("content") or chunk.get("text") or "")
    context = "\n\n---\n\n".join(t for t in texts if t)

    if not context:
        return FaithfulnessResult(
            score=0.0, num_claims=0, supported=0,
            contradicted=0, not_found=0, error="컨텍스트 없음"
        )

    try:
        claims = _extract_claims(answer)
    except Exception as e:
        return FaithfulnessResult(
            score=0.0, num_claims=0, supported=0,
            contradicted=0, not_found=0, error=f"claim 추출 실패: {e}"
        )

    if not claims:
        return FaithfulnessResult(
            score=1.0, num_claims=0, supported=0,
            contradicted=0, not_found=0
        )

    verdicts = []
    for claim in claims:
        try:
            verdicts.append(_verify_claim(claim, context))
        except Exception as e:
            verdicts.append({"claim": claim, "verdict": "NOT_FOUND", "evidence": str(e)})

    supported     = sum(1 for v in verdicts if v["verdict"] == "SUPPORTED")
    contradicted  = sum(1 for v in verdicts if v["verdict"] == "CONTRADICTED")
    not_found     = sum(1 for v in verdicts if v["verdict"] == "NOT_FOUND")
    score = supported / len(claims) if claims else 0.0

    return FaithfulnessResult(
        score=score,
        num_claims=len(claims),
        supported=supported,
        contradicted=contradicted,
        not_found=not_found,
        claim_verdicts=verdicts,
    )
