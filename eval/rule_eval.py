"""
Rule-based 평가 모듈
- 여행 일정 답변의 구조적 유효성 검사
  1. 세션 개수 : 요청한 일수 × 하루 세션 수와 일치하는지
  2. 시간 합계 : 하루 총 소요시간이 허용 범위(기본 4~10시간) 내인지
  3. 그룹 구성 : 지정된 그룹 유형(휠체어/고령자/유아) 대응 언급 여부
- 정규표현식으로 구조 파싱, 외부 API 불필요
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field


# ── 헬퍼 ────────────────────────────────────────────────────────────────────

_TIME_PATTERN = re.compile(
    r"(\d+)\s*시간\s*(?:(\d+)\s*분)?|(\d+)\s*분"
)

def _parse_minutes(text: str) -> int:
    """텍스트에서 시간 표현을 파싱해 분 단위로 반환 (없으면 0)"""
    total = 0
    for m in _TIME_PATTERN.finditer(text):
        h  = int(m.group(1)) if m.group(1) else 0
        mi = int(m.group(2)) if m.group(2) else 0
        only_min = int(m.group(3)) if m.group(3) else 0
        total += h * 60 + mi + only_min
    return total


_SESSION_HEADERS = re.compile(
    r"(?:오전|오후|아침|점심|저녁|day\s*\d+|일차|세션|\d+\s*일\s*차)",
    re.IGNORECASE,
)

_GROUP_KEYWORDS: dict[str, list[str]] = {
    "wheelchair": ["휠체어", "배리어프리", "무장애", "경사로", "단차"],
    "elderly":    ["고령자", "노인", "어르신", "시니어"],
    "infant":     ["유아", "영아", "유모차", "아기"],
}


# ── 결과 타입 ────────────────────────────────────────────────────────────────

@dataclass
class RuleCheckItem:
    rule: str
    passed: bool
    detail: str


@dataclass
class RuleEvalResult:
    passed: bool
    score: float                          # 통과 규칙 수 / 전체 규칙 수
    checks: list[RuleCheckItem] = field(default_factory=list)


# ── 개별 규칙 검사 ────────────────────────────────────────────────────────────

def check_session_count(
    answer: str,
    expected_days: int,
    sessions_per_day: int = 3,
) -> RuleCheckItem:
    """
    답변에 포함된 세션 헤더 수가 expected_days × sessions_per_day ± 허용 오차(1)인지 확인.
    """
    found = len(_SESSION_HEADERS.findall(answer))
    expected = expected_days * sessions_per_day
    passed = abs(found - expected) <= 1
    return RuleCheckItem(
        rule="session_count",
        passed=passed,
        detail=f"발견된 세션 헤더: {found}개 / 기대값: {expected}개",
    )


def check_daily_time(
    answer: str,
    min_hours: float = 4.0,
    max_hours: float = 10.0,
) -> RuleCheckItem:
    """
    답변에서 파싱된 총 소요시간이 하루 허용 범위 내인지 확인.
    시간 표현이 없으면 SKIP(통과 처리).
    """
    total_min = _parse_minutes(answer)
    if total_min == 0:
        return RuleCheckItem(
            rule="daily_time",
            passed=True,
            detail="시간 표현 없음 (검사 SKIP)",
        )
    total_hours = total_min / 60
    passed = min_hours <= total_hours <= max_hours
    return RuleCheckItem(
        rule="daily_time",
        passed=passed,
        detail=f"파싱된 총 시간: {total_hours:.1f}h (허용: {min_hours}~{max_hours}h)",
    )


def check_group_composition(
    answer: str,
    required_groups: list[str],
) -> RuleCheckItem:
    """
    required_groups에 지정된 그룹 유형 키워드가 답변에 언급되는지 확인.

    required_groups 항목: "wheelchair" | "elderly" | "infant" | 임의 문자열
    """
    if not required_groups:
        return RuleCheckItem(
            rule="group_composition",
            passed=True,
            detail="그룹 요구사항 없음",
        )

    missing = []
    for group in required_groups:
        keywords = _GROUP_KEYWORDS.get(group, [group])
        if not any(kw in answer for kw in keywords):
            missing.append(group)

    passed = len(missing) == 0
    detail = (
        f"모든 그룹 언급 확인" if passed
        else f"미언급 그룹: {', '.join(missing)}"
    )
    return RuleCheckItem(rule="group_composition", passed=passed, detail=detail)


# ── 통합 평가 ────────────────────────────────────────────────────────────────

def evaluate_rules(
    answer: str,
    expected_days: int = 1,
    sessions_per_day: int = 3,
    min_hours: float = 4.0,
    max_hours: float = 10.0,
    required_groups: list[str] | None = None,
) -> RuleEvalResult:
    """
    규칙 기반 평가 통합 실행.

    Args:
        answer:           RAG 시스템이 생성한 답변
        expected_days:    여행 일수
        sessions_per_day: 하루 세션 수 (기본 3 = 오전/오후/저녁)
        min_hours:        하루 최소 소요시간 (기본 4h)
        max_hours:        하루 최대 소요시간 (기본 10h)
        required_groups:  필수 그룹 유형 목록

    Returns:
        RuleEvalResult
    """
    checks = [
        check_session_count(answer, expected_days, sessions_per_day),
        check_daily_time(answer, min_hours, max_hours),
        check_group_composition(answer, required_groups or []),
    ]
    passed_count = sum(1 for c in checks if c.passed)
    score = passed_count / len(checks)
    return RuleEvalResult(
        passed=all(c.passed for c in checks),
        score=score,
        checks=checks,
    )
