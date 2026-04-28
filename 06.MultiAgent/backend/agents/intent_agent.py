"""
IntentAgent — 사용자 메시지에서 여행 의도를 구조화된 TravelIntent로 파싱합니다.
"""
from __future__ import annotations
import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from ..schemas import TravelIntent

load_dotenv()

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "intent_agent.txt")


class IntentAgent:
    def __init__(self) -> None:
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
            self._system_prompt = f.read()

    def run(self, user_message: str) -> TravelIntent:
        response = self._client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        data = json.loads(response.choices[0].message.content)
        print(f"[IntentAgent] parsed: {data}")
        return TravelIntent(**data)
