"""
ItineraryAgent — 검증된 장소로 일별 여행 일정을 생성합니다.
"""
from __future__ import annotations
import os
import json
from typing import List
from openai import OpenAI
from dotenv import load_dotenv
from ..schemas import TravelIntent, ValidationResult, Itinerary, ItineraryDay, DaySession

load_dotenv()

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "itinerary_agent.txt")


class ItineraryAgent:
    def __init__(self) -> None:
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
            self._system_prompt = f.read()

    def run(
        self,
        intent: TravelIntent,
        safe_places: List[ValidationResult],
        validation_failures: List[dict],
    ) -> Itinerary:
        safe_names = [v.place_name for v in safe_places]
        flagged_names = [f.get("place_name", "") for f in validation_failures]

        user_content = f"""[여행 조건]
- 목적지: {intent.destination}
- 기간: {intent.duration_days}일
- 접근성 조건: {', '.join(intent.accessibility_needs)}
- 그룹: {', '.join(intent.group_types) or '없음'}
{f'- 특별 요청: {intent.special_requests}' if intent.special_requests else ''}

✅ 사용 가능한 장소 (검증 통과): {', '.join(safe_names) if safe_names else '없음'}
🔴 제외된 장소 (접근성 미달): {', '.join(flagged_names) if flagged_names else '없음'}

{intent.duration_days}일 일정을 JSON으로 생성하세요.
형식:
{{
  "days": [
    {{
      "day": 1,
      "sessions": [
        {{"session": "오전", "place": "장소명", "duration_hours": 2.0, "accessibility_notes": "접근성 설명", "validation_status": "✅"}}
      ],
      "total_hours": 5.0
    }}
  ],
  "summary_markdown": "## 여행 일정\\n\\n### 1일차\\n..."
}}
"""
        response = self._client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        data = json.loads(response.choices[0].message.content)
        print(f"[ItineraryAgent] generated {len(data.get('days', []))} days")

        days = []
        for d in data.get("days", []):
            sessions = [DaySession(**s) for s in d.get("sessions", [])]
            days.append(ItineraryDay(
                day=d["day"],
                sessions=sessions,
                total_hours=d.get("total_hours", sum(s.duration_hours for s in sessions)),
            ))

        return Itinerary(
            destination=intent.destination,
            duration_days=intent.duration_days,
            accessibility_needs=intent.accessibility_needs,
            group_types=intent.group_types,
            days=days,
            summary_markdown=data.get("summary_markdown", ""),
        )
