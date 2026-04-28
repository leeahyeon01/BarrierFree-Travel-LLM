"""
ValidationAgent — 각 장소의 접근성을 검증합니다.
NaverAccessibilityValidator 사용 가능 시 실제 검증을 수행하고,
불가능하면 LLM 기반 fallback으로 처리합니다.
"""
from __future__ import annotations
import os
import sys
import json
from typing import List
from openai import OpenAI
from dotenv import load_dotenv
from ..schemas import PlaceInfo, ValidationResult

load_dotenv()

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "validation_agent.txt")

# NaverAccessibilityValidator 동적 임포트 (부모 프로젝트)
_PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

try:
    from naver_validator import NaverAccessibilityValidator
    _naver_validator = NaverAccessibilityValidator()
    _HAS_NAVER = True
except Exception:
    _HAS_NAVER = False


class ValidationAgent:
    def __init__(self) -> None:
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
            self._system_prompt = f.read()

    def run(
        self,
        places: List[PlaceInfo],
        accessibility_needs: List[str],
    ) -> List[ValidationResult]:
        results = []
        for place in places:
            result = self._validate(place, accessibility_needs)
            print(f"[ValidationAgent] {place.name} → {'✅' if result.is_safe else '🔴'}")
            results.append(result)
        return results

    # ── 실제 검증 ──────────────────────────────────────────────────────────────

    def _validate(self, place: PlaceInfo, accessibility_needs: List[str]) -> ValidationResult:
        if _HAS_NAVER:
            try:
                return self._naver_validate(place, accessibility_needs)
            except Exception:
                pass
        return self._llm_validate(place, accessibility_needs)

    def _naver_validate(self, place: PlaceInfo, accessibility_needs: List[str]) -> ValidationResult:
        raw = _naver_validator.validate(place.name)
        issues = []
        if not raw.get("accessible_entrance", True):
            issues.append("입구 접근 불가")
        if "휠체어" in accessibility_needs and not raw.get("wheelchair_accessible", True):
            issues.append("휠체어 이용 불가")
        if not raw.get("accessible_restroom", True):
            issues.append("장애인 화장실 없음")

        return ValidationResult(
            place_name=place.name,
            is_safe=len(issues) == 0,
            accessibility_score=raw.get("confidence_score"),
            issues=issues,
            evidence=raw.get("evidence", []),
            inference_note=raw.get("inference_note"),
        )

    def _llm_validate(self, place: PlaceInfo, accessibility_needs: List[str]) -> ValidationResult:
        user_content = f"""장소: {place.name}
카테고리: {place.category}
접근성 정보: {place.accessibility_summary}
필요 접근성 조건: {', '.join(accessibility_needs)}

이 장소가 위 조건을 만족하는지 검증하세요.
JSON 반환: {{"is_safe": true/false, "issues": ["문제1"], "evidence": ["근거1"], "inference_note": "추론 근거"}}
"""
        response = self._client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        data = json.loads(response.choices[0].message.content)
        return ValidationResult(
            place_name=place.name,
            is_safe=data.get("is_safe", True),
            issues=data.get("issues", []),
            evidence=data.get("evidence", []),
            inference_note=data.get("inference_note"),
        )
