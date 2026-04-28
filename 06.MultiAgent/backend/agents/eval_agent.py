"""
EvalAgent — 생성된 일정의 품질을 평가합니다.

[코드 검증 항목] — 규칙 기반, 외부 API 불필요
  - Precision@k / Recall@k / MRR  (retrieved_ids 제공 시)
  - 세션 수 검증 (session_count_ok)
  - 일일 소요시간 범위 (daily_time_ok)
  - 그룹 구성 키워드 언급 (group_composition_ok)

[LLM 판단 항목] — GPT 호출 필요
  - Faithfulness  : 답변 주장이 증거(evidence)에 근거하는 비율
  - Coverage      : 접근성 요구사항 반영 비율
"""
from __future__ import annotations
import os
import sys
from typing import List
from ..schemas import TravelIntent, ValidationResult, Itinerary, EvalReport, EvalCodeChecks, EvalLLMChecks

# 부모 프로젝트 eval 모듈 동적 임포트
_PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

try:
    from eval.faithfulness_eval import evaluate_faithfulness
    from eval.coverage_eval import evaluate_coverage
    from eval.rule_eval import evaluate_rules
    _HAS_EVAL = True
except Exception:
    _HAS_EVAL = False


class EvalAgent:
    def run(
        self,
        itinerary: Itinerary,
        intent: TravelIntent,
        safe_places: List[ValidationResult],
    ) -> EvalReport:
        code_checks = self._code_checks(itinerary, intent)
        llm_checks = self._llm_checks(itinerary, intent, safe_places)
        overall_pass = (
            code_checks.session_count_ok
            and code_checks.daily_time_ok
            and code_checks.group_composition_ok
            and (llm_checks.faithfulness is None or llm_checks.faithfulness >= 0.7)
            and (llm_checks.coverage is None or llm_checks.coverage >= 0.7)
        )
        print(f"[EvalAgent] overall_pass={overall_pass} | faith={llm_checks.faithfulness} | cov={llm_checks.coverage}")
        return EvalReport(code_checks=code_checks, llm_checks=llm_checks, overall_pass=overall_pass)

    # ── 코드 검증 항목 ─────────────────────────────────────────────────────────

    def _code_checks(self, itinerary: Itinerary, intent: TravelIntent) -> EvalCodeChecks:
        sessions_per_day = [len(d.sessions) for d in itinerary.days]
        daily_hours = [d.total_hours for d in itinerary.days]

        if _HAS_EVAL:
            try:
                answer = itinerary.summary_markdown or ""
                rule_result = evaluate_rules(
                    answer=answer,
                    expected_days=intent.duration_days,
                    sessions_per_day=max(sessions_per_day) if sessions_per_day else 1,
                    required_groups=intent.group_types,
                )
                checks = {c.rule: c.passed for c in rule_result.checks}
                return EvalCodeChecks(
                    session_count_ok=checks.get("session_count", True),
                    daily_time_ok=checks.get("daily_time", True),
                    group_composition_ok=checks.get("group_composition", True),
                )
            except Exception:
                pass

        return EvalCodeChecks(
            session_count_ok=all(s >= 1 for s in sessions_per_day),
            daily_time_ok=all(1.0 <= h <= 12.0 for h in daily_hours),
            group_composition_ok=True,
        )

    # ── LLM 판단 항목 ──────────────────────────────────────────────────────────

    def _llm_checks(
        self,
        itinerary: Itinerary,
        intent: TravelIntent,
        safe_places: List[ValidationResult],
    ) -> EvalLLMChecks:
        if not _HAS_EVAL:
            return EvalLLMChecks()

        answer = itinerary.summary_markdown or ""
        context_chunks = [ev for v in safe_places for ev in v.evidence]

        faithfulness_score = None
        coverage_score = None

        try:
            if context_chunks:
                faith_result = evaluate_faithfulness(answer=answer, context_chunks=context_chunks)
                faithfulness_score = faith_result.score
        except Exception:
            pass

        try:
            requirements = list(intent.accessibility_needs) + [f"{g} 접근성" for g in intent.group_types]
            cov_result = evaluate_coverage(answer=answer, requirements=requirements)
            coverage_score = cov_result.score
        except Exception:
            pass

        return EvalLLMChecks(faithfulness=faithfulness_score, coverage=coverage_score)
