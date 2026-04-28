"""
OrchestratorAgent — 전체 멀티에이전트 파이프라인을 조율합니다.

파이프라인:
  1. IntentAgent     : 사용자 메시지 → TravelIntent
  2. PlaceSearchAgent: TravelIntent + 제외 목록 → 후보 장소 목록
  3. ValidationAgent : 후보 장소 → ✅ 안전 / 🔴 위험 분류
     └─ 안전 장소가 부족하면 PlaceSearchAgent를 재호출 (최대 2회 재시도)
  4. ItineraryAgent  : 안전 장소 → 일별 여행 일정
  5. EvalAgent       : 일정 품질 평가 (코드 검증 + LLM 판단)
"""
from __future__ import annotations
from typing import List

from .agents.intent_agent import IntentAgent
from .agents.place_search_agent import PlaceSearchAgent
from .agents.validation_agent import ValidationAgent
from .agents.itinerary_agent import ItineraryAgent
from .agents.eval_agent import EvalAgent
from .schemas import ChatResponse, TravelIntent, ValidationResult, Itinerary, EvalReport


class OrchestratorAgent:
    _MIN_SAFE_PLACES_PER_DAY = 2
    _MAX_RETRIES = 2

    def __init__(self) -> None:
        self._intent = IntentAgent()
        self._search = PlaceSearchAgent()
        self._validation = ValidationAgent()
        self._itinerary = ItineraryAgent()
        self._eval = EvalAgent()

    def run(self, user_message: str) -> ChatResponse:
        # ── 1. 의도 파싱 ───────────────────────────────────────────────────────
        intent: TravelIntent = self._intent.run(user_message)
        print(f"[Orchestrator] intent: {intent.destination} / {intent.duration_days}일 / {intent.accessibility_needs}")

        # ── 2+3. 검색 → 검증 (재시도 포함) ────────────────────────────────────
        safe_places: List[ValidationResult] = []
        validation_failures: List[dict] = []   # 🔴 위험 장소 (dict 형태로 누적)
        min_needed = intent.duration_days * self._MIN_SAFE_PLACES_PER_DAY

        for attempt in range(self._MAX_RETRIES + 1):
            already_excluded = [f["place_name"] for f in validation_failures]
            candidates = self._search.run(intent=intent, exclude_places=already_excluded)

            if not candidates:
                break

            validations = self._validation.run(candidates, intent.accessibility_needs)

            newly_safe = [v for v in validations if v.is_safe]
            newly_flagged = [v for v in validations if not v.is_safe]

            safe_places.extend(newly_safe)
            validation_failures.extend([self._to_dict(v) for v in newly_flagged])

            print(f"[Orchestrator] attempt {attempt+1}: safe={len(safe_places)} / flagged={len(validation_failures)}")

            if len(safe_places) >= min_needed:
                break

        # ── 4. 일정 생성 ───────────────────────────────────────────────────────
        itinerary: Itinerary = self._itinerary.run(intent, safe_places, validation_failures)

        # ── 5. 평가 ────────────────────────────────────────────────────────────
        eval_report: EvalReport = self._eval.run(itinerary, intent, safe_places)

        # ── 6. 응답 조립 ───────────────────────────────────────────────────────
        reply = self._build_reply(itinerary, validation_failures, eval_report)
        itinerary_dict = self._to_dict(itinerary)

        return ChatResponse(
            reply=reply,
            complete=True,
            itinerary=itinerary_dict,
            validation_result={
                "safe_places": [v.place_name for v in safe_places],
                "flagged_places": validation_failures,
                "eval_scores": self._to_dict(eval_report),
            },
        )

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    @staticmethod
    def _to_dict(obj) -> dict:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        return {}

    def _build_reply(
        self,
        itinerary: Itinerary,
        validation_failures: List[dict],
        eval_report: EvalReport,
    ) -> str:
        lines: List[str] = []

        # 🔴 접근성 경고
        if validation_failures:
            lines.append(f"⚠️ **접근성 경고**: {len(validation_failures)}개 장소가 검증에서 제외되었습니다.")
            for f in validation_failures:
                issues = ", ".join(f.get("issues", ["접근성 미달"]))
                lines.append(f"- 🔴 **{f.get('place_name', '?')}**: {issues}")
            lines.append("")

        # 일정 본문
        if itinerary.summary_markdown:
            lines.append(itinerary.summary_markdown)
        else:
            lines.append(f"## {itinerary.destination} {itinerary.duration_days}일 무장애 여행 일정\n")
            for day in itinerary.days:
                lines.append(f"\n### {day.day}일차")
                for s in day.sessions:
                    lines.append(
                        f"- **{s.session}** | {s.place} ({s.duration_hours}h) "
                        f"{s.validation_status} — {s.accessibility_notes}"
                    )
                lines.append(f"  *하루 총 {day.total_hours}시간*")

        # 평가 요약
        cc = eval_report.code_checks
        lc = eval_report.llm_checks
        lines.append("\n---\n**평가 결과**")
        lines.append(
            f"- 세션 수: {'✅' if cc.session_count_ok else '❌'} "
            f"| 일일 시간: {'✅' if cc.daily_time_ok else '❌'} "
            f"| 그룹 조건: {'✅' if cc.group_composition_ok else '❌'}"
        )
        if lc.faithfulness is not None:
            lines.append(f"- 충실도: {lc.faithfulness:.2f} | 요구사항 반영: {lc.coverage:.2f}")
        if cc.precision_at_k is not None:
            lines.append(f"- Precision@k: {cc.precision_at_k:.2f} | Recall@k: {cc.recall_at_k:.2f} | MRR: {cc.mrr:.2f}")

        return "\n".join(lines)
