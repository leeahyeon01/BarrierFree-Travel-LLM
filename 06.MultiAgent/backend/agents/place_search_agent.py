"""
PlaceSearchAgent — RAG에서 접근성 조건에 맞는 장소를 검색하고 LLM으로 후처리합니다.
중복 RAG 호출을 방지하기 위해 retrieval.py를 단일 진입점으로 사용합니다.
"""
from __future__ import annotations
import os
import json
from typing import List, Optional
from openai import OpenAI
from dotenv import load_dotenv
from ..schemas import TravelIntent, PlaceInfo
from ..retrieval import retrieve_places

load_dotenv()

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "place_search_agent.txt")


class PlaceSearchAgent:
    def __init__(self) -> None:
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
            self._system_prompt = f.read()

    def run(
        self,
        intent: TravelIntent,
        exclude_places: Optional[List[str]] = None,
    ) -> List[PlaceInfo]:
        exclude_places = exclude_places or []

        raw_results = retrieve_places(
            destination=intent.destination,
            accessibility_needs=intent.accessibility_needs,
            top_k=15,
        )

        # 제외 목록 필터링
        filtered = [r for r in raw_results if r.get("name", "") not in exclude_places]

        context = json.dumps(filtered, ensure_ascii=False, indent=2)
        user_content = f"""목적지: {intent.destination}
기간: {intent.duration_days}일
접근성 조건: {', '.join(intent.accessibility_needs)}
그룹: {', '.join(intent.group_types) or '없음'}
특별 요청: {intent.special_requests or '없음'}
제외 장소: {', '.join(exclude_places) or '없음'}

[RAG 검색 결과]
{context}

위 결과에서 조건에 맞는 장소를 JSON으로 반환하세요.
형식: {{"places": [{{"name": "장소명", "category": "tourist|restaurant|transport", "accessibility_summary": "접근성 설명", "source": "출처"}}]}}
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
        places_list = data.get("places", [])
        print(f"[PlaceSearchAgent] found {len(places_list)} places")
        return [PlaceInfo(**p) for p in places_list if isinstance(p, dict)]
