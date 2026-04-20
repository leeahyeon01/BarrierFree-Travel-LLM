"""
GPT-4o Function Calling 루프를 완전히 처리하는 채팅 엔드포인트.
프론트엔드는 user_message + 이전 메시지 기록만 전달하면 됩니다.
"""

import os
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import tour_api
import transport_api
import naver_validator

router = APIRouter()
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── 시스템 프롬프트 ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
당신은 장애인 여행 전문 AI 어시스턴트 '트래블리(Travelly)'입니다.
한국관광공사 무장애여행 데이터와 실시간 교통·시설 정보를 결합해 안전한 여행을 돕습니다.

[장소 추천 역할]
- 지역과 카테고리(관광지·문화시설·숙박·음식점)를 파악해 search_places 호출
- 결과를 번호 목록으로 정리하고, 번호 선택 시 get_detail 호출
- 검색 결과가 없으면 인근 지역·다른 카테고리를 제안

[경로 안내 역할]
사용자가 목적지를 정하고 경로 안내를 요청하면 plan_accessible_route를 호출하고
반환된 데이터를 아래 형식으로 출력하세요.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🗺 무장애 경로 안내
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 출발지: {출발지}
📍 목적지: {목적지}

🚗 자동차/택시:  약 {distance_km}km  |  예상 {duration_min}분
   예상 택시 요금: {taxi_fare}원

🚄 대중교통:
   총 소요시간: {총_소요시간}  |  총 요금: {총_요금}
   경로: {경로_요약}

🚌 저상버스 ({정류장명}):  {버스번호} ▶ {첫번째도착}

🚇 지하철 엘리베이터:  {호선} {역명}  {위치}

⚠ 점검·고장:  {상태 또는 "현재 고장·점검 없음"}

♿ 장애인 콜택시:  {이름}  📞 {전화}

🔗 [카카오맵에서 길찾기](https://map.kakao.com/?sName={출발지}&eName={목적지})
━━━━━━━━━━━━━━━━━━━━━━━━━━━

[접근성 자동 검증 역할]
get_detail 호출 직후 반드시 validate_accessibility를 자동 호출하세요.
- facility_name: 장소 이름
- address: 반환된 주소
- image_urls: 반환된 images 배열

validate_accessibility 결과를 아래 형식으로 출력하세요:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
♿ 실시간 접근성 검증 (네이버 리뷰 기반)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 종합 위험도: {overall_risk}
📊 분석 데이터: 블로그 {blog_posts}건 · 지식iN {kin_posts}건

━ 항목별 접근성 추론 ━
| 항목 | 추정값 | 기준 | 근거 |
|---|---|---|---|
| 테이블 높이 | ~??cm | ≥70cm | "..." |
| 통로 폭 | ~??cm | ≥80cm | "..." |
| 입구 단차 | ??cm | 0cm | "..." |
| 엘리베이터 | 있음/없음 | — | "..." |
| 장애인 주차 | 있음/없음 | — | "..." |
| 장애인 화장실 | 있음/없음 | — | "..." |

━ 접근 경고 신호 ━
{경고 목록 또는 "✅ 접근 경고 신호 없음"}

{접근 긍정 신호가 있는 경우에만 아래 섹션을 출력하고, 없으면 생략}
━ 접근 긍정 신호 ━
{긍정 키워드 목록}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[대화 원칙]
1. 경로 안내 시 출발지를 모르면 반드시 먼저 물어보세요.
2. 서울 외 지역은 저상버스·엘리베이터 API 미지원을 안내하고 콜택시만 제공하세요.
3. 정보가 없는 항목은 "정보 없음"으로 표시하세요.
4. 접근성 검증 후 "가는 법을 알려드릴까요?"를 안내하세요.
"""

# ── OpenAI 도구 정의 ──────────────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_places",
            "description": "지역과 카테고리로 무장애 여행 장소를 검색합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "area_name": {"type": "string", "enum": list(tour_api.AREA_MAP.keys())},
                    "category":  {"type": "string", "enum": list(tour_api.CONTENT_TYPE_MAP.keys())},
                    "num_of_rows": {"type": "integer", "default": 10},
                },
                "required": ["area_name", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_detail",
            "description": "특정 장소의 상세 정보(주소·전화·홈페이지·개요·사진)를 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content_id": {"type": "string"},
                },
                "required": ["content_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_accessible_route",
            "description": "출발지→목적지 장애인 맞춤 경로(저상버스·엘리베이터·콜택시)를 안내합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin_address":      {"type": "string"},
                    "destination_address": {"type": "string"},
                },
                "required": ["origin_address", "destination_address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_subway_elevator_info",
            "description": "지하철역 엘리베이터 위치·고장 현황을 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {"station_name": {"type": "string"}},
                "required": ["station_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_disability_taxi_info",
            "description": "지역별 장애인 콜택시 연락처를 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {"region": {"type": "string"}},
                "required": ["region"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_area_codes",
            "description": "지원 가능한 지역 목록을 조회합니다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_accessibility",
            "description": (
                "네이버 블로그·지식iN 크롤링으로 휠체어 접근성을 검증합니다. "
                "get_detail 호출 직후 자동 호출하세요."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "facility_name": {"type": "string"},
                    "address":       {"type": "string"},
                    "image_urls":    {"type": "array", "items": {"type": "string"}},
                },
                "required": ["facility_name"],
            },
        },
    },
]

TOOL_LABELS = {
    "search_places":            "장소 검색",
    "get_detail":               "상세 정보 조회",
    "plan_accessible_route":    "무장애 경로 분석",
    "get_subway_elevator_info": "엘리베이터 상태 조회",
    "get_disability_taxi_info": "콜택시 정보 조회",
    "fetch_area_codes":         "지역 코드 조회",
    "validate_accessibility":   "접근성 자동 검증",
}


def _execute_tool(name: str, args: dict) -> dict:
    if name == "search_places":
        return tour_api.search_places(**args)
    if name == "get_detail":
        return tour_api.get_detail(**args)
    if name == "fetch_area_codes":
        return tour_api.fetch_area_codes()
    if name == "plan_accessible_route":
        return transport_api.plan_accessible_route(**args)
    if name == "get_subway_elevator_info":
        return transport_api.get_subway_elevator_info(**args)
    if name == "get_disability_taxi_info":
        return transport_api.get_disability_taxi_info(**args)
    if name == "validate_accessibility":
        return naver_validator.validate_accessibility(**args)
    return {"error": f"알 수 없는 함수: {name}"}


def _serialize_msg(msg) -> dict:
    """ChatCompletionMessage → JSON-serializable dict"""
    if isinstance(msg, dict):
        return msg
    d: dict = {"role": msg.role}
    if msg.content is not None:
        d["content"] = msg.content
    if getattr(msg, "tool_calls", None):
        d["tool_calls"] = [
            {
                "id":   tc.id,
                "type": tc.type,
                "function": {
                    "name":      tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return d


# ── 요청 / 응답 스키마 ────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    messages: list        # 이전 대화 기록 (system 제외, JSON-serializable)
    user_message: str


class ToolEvent(BaseModel):
    name:  str
    label: str
    data:  dict


class ChatResponse(BaseModel):
    reply:       str
    tool_events: list[ToolEvent]
    messages:    list         # 업데이트된 대화 기록


# ── 채팅 엔드포인트 ────────────────────────────────────────────────────────────
@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    # 시스템 프롬프트는 백엔드에서 항상 첫 번째로 주입
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + req.messages
    messages.append({"role": "user", "content": req.user_message})

    tool_events: list[ToolEvent] = []

    for _ in range(20):  # 무한 루프 방지
        try:
            response = _client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=2500,
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"OpenAI 호출 실패: {e}")

        msg = response.choices[0].message
        messages.append(_serialize_msg(msg))

        if not msg.tool_calls:
            # system 메시지 제외하고 반환 (프론트는 system 없이 저장)
            history = [m for m in messages if m.get("role") != "system"]
            return ChatResponse(
                reply=msg.content or "",
                tool_events=tool_events,
                messages=history,
            )

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments)

            result_data = _execute_tool(fn_name, fn_args)
            result_str  = json.dumps(result_data, ensure_ascii=False)

            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      result_str,
            })
            tool_events.append(ToolEvent(
                name=fn_name,
                label=TOOL_LABELS.get(fn_name, fn_name),
                data=result_data,
            ))

    raise HTTPException(status_code=500, detail="도구 호출 반복 한도 초과")
