"""
♿ 무장애 여행 추천 챗봇 '트래블리(Travelly)'
- 장소 추천  : 한국관광공사 KorWithService2 API
- 경로 안내  : Kakao Mobility / 서울시 버스 / 서울 열린데이터광장
- AI 대화    : OpenAI GPT-4o Function Calling
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv
import tour_api
import transport_api
import naver_validator

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── 시스템 프롬프트 ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
당신은 장애인 여행 전문 AI 어시스턴트 '트래블리(Travelly)'입니다.
한국관광공사 무장애여행 데이터와 실시간 교통·시설 정보를 결합해 안전한 여행을 돕습니다.

[장소 추천 역할]
- 지역과 카테고리(관광지·문화시설·숙박·음식점)를 파악해 search_places 호출
- 결과를 번호 목록으로 정리하고, 번호 선택 시 get_detail 호출
- 검색 결과가 없으면 인근 지역·다른 카테고리를 제안

[경로 안내 역할]
사용자가 목적지를 정하고 챗봇에게 어떻게 가냐고 물어보는 등 경로 안내를 요청하면 plan_accessible_route 를 호출하고,
반환된 데이터를 반드시 아래 형식으로 출력하세요. 카카오맵 대중교통 링크도 제공하세요.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🗺 무장애 경로 안내
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 출발지: {출발지}
📍 목적지: {목적지}

🚗 자동차/택시:  약 {distance_km}km  |  예상 {duration_min}분
   예상 택시 요금: {taxi_fare}원

🚄 대중교통 (기차/고속버스/지하철 환승):
   총 소요시간: {총_소요시간}  |  총 요금: {총_요금}
   경로: {경로_요약}
   상세: {상세_환승_단계}

🚌 출발지 근처 저상버스 ({정류장명}):
   {버스번호} ({저상버스여부})  ▶  {첫번째도착}

🚇 지하철 엘리베이터:
   {호선} {역명}  {위치}  — 엘리베이터 이용 권장

⚠ 점검·고장 현황:
   {상태가 있으면 역명 + 위치 + 상태 표시, 없으면 "현재 고장·점검 없음"}

♿ 장애인 콜택시 ({region}):
   {이름}  |  📞 {전화}  |  앱: {앱}

💡 참고사항:
   {참고사항 목록}
   
🔗 대중교통 카카오맵: [카카오맵에서 길찾기](https://map.kakao.com/?sName={출발지}&eName={목적지})
━━━━━━━━━━━━━━━━━━━━━━━━━━━

[접근성 자동 검증 역할] ← 핵심
get_detail 호출로 장소 상세 정보를 받은 직후, 반드시 validate_accessibility를 자동 호출하세요.
- facility_name: 장소 이름
- address: 반환된 주소
- image_urls: 반환된 images 배열 (있으면 전달)

validate_accessibility 결과를 아래 형식으로 출력하세요:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
♿ 실시간 접근성 검증 (네이버 리뷰 기반)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 종합 위험도: {overall_risk}
📊 분석 데이터: 블로그 {blog_posts}건 · 지식iN {kin_posts}건

━ 항목별 접근성 추론 ━
┌──────────────┬──────────┬─────────┬──────────────────────────────┐
│ 항목          │ 추정값   │ 기준    │ 근거 리뷰 인용               │
├──────────────┼──────────┼─────────┼──────────────────────────────┤
│ 테이블 높이   │ ~??cm    │ ≥70cm  │ "..."                        │
│ 통로 폭       │ ~??cm    │ ≥80cm  │ "..."                        │
│ 입구 단차     │ ??cm     │ 0cm    │ "..."                        │
│ 엘리베이터    │ 있음/없음│ —      │ "..."                        │
│ 장애인 주차   │ 있음/없음│ —      │ "..."                        │
│ 장애인 화장실 │ 있음/없음│ —      │ "..."                        │
└──────────────┴──────────┴─────────┴──────────────────────────────┘

━ 경고 신호 ━
{경고가 있으면 각 항목을 severity · category · 리뷰 인용 형식으로 나열}
{경고 없으면 "✅ 리뷰에서 접근성 문제 발견되지 않음"}

━ 공식 정보 불일치 ━
{불일치 항목 · 근거 또는 "불일치 없음"}

━ 긍정 신호 ━
{긍정 키워드 목록 또는 "없음"}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[대화 원칙]
1. 경로 안내 시 출발지를 모르면 반드시 먼저 물어보세요.
2. 서울 외 지역은 저상버스·엘리베이터 API 미지원임을 안내하고 콜택시 정보만 제공하세요.
3. 정보가 없는 항목은 "정보 없음"으로 표시하고 생략하지 마세요.
4. 장애 유형별 추가 팁(시각장애, 지체장애 등)이 있으면 덧붙이세요.
5. 접근성 검증 후 "가는 법을 알려드릴까요? (출발지를 입력해 주세요.)"를 안내하세요.
"""

# ── OpenAI Function Calling 도구 정의 ────────────────────────────────────────
TOOLS = [
    # ── 장소 검색 ────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "search_places",
            "description": "지역과 카테고리로 무장애 여행 장소(관광지·문화시설·숙박·음식점)를 검색합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "area_name": {
                        "type": "string",
                        "description": "검색할 지역명",
                        "enum": list(tour_api.AREA_MAP.keys()),
                    },
                    "category": {
                        "type": "string",
                        "description": "검색할 카테고리",
                        "enum": list(tour_api.CONTENT_TYPE_MAP.keys()),
                    },
                    "num_of_rows": {
                        "type": "integer",
                        "description": "조회 건수 (기본 10, 최대 20)",
                        "default": 10,
                    },
                },
                "required": ["area_name", "category"],
            },
        },
    },
    # ── 장소 상세 ────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_detail",
            "description": "특정 장소의 상세 정보(주소·전화·홈페이지·개요)를 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content_id": {
                        "type": "string",
                        "description": "조회할 장소의 content_id (검색 결과에 포함된 값)",
                    },
                },
                "required": ["content_id"],
            },
        },
    },
    # ── 무장애 경로 통합 안내 ─────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "plan_accessible_route",
            "description": (
                "출발지에서 목적지까지 장애인 맞춤 경로를 안내합니다. "
                "저상버스 도착 정보, 지하철 엘리베이터 위치, 리프트 고장 현황, "
                "장애인 콜택시 정보를 한 번에 조회합니다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin_address": {
                        "type": "string",
                        "description": "출발지 주소 또는 장소명 (예: '서울 마포구 홍대입구역')",
                    },
                    "destination_address": {
                        "type": "string",
                        "description": "목적지 주소 또는 장소명 (예: '서울 강남구 코엑스')",
                    },
                },
                "required": ["origin_address", "destination_address"],
            },
        },
    },
    # ── 엘리베이터 개별 조회 ──────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_subway_elevator_info",
            "description": "특정 지하철역의 엘리베이터 위치와 고장 현황을 조회합니다. (서울 지하철 한정)",
            "parameters": {
                "type": "object",
                "properties": {
                    "station_name": {
                        "type": "string",
                        "description": "조회할 지하철역명 (예: '강남역', '홍대입구역')",
                    },
                },
                "required": ["station_name"],
            },
        },
    },
    # ── 장애인 콜택시 개별 조회 ───────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_disability_taxi_info",
            "description": "지역별 장애인 콜택시 연락처와 예약 앱 정보를 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "description": "조회할 지역명 (예: '서울', '부산', '제주')",
                    },
                },
                "required": ["region"],
            },
        },
    },
    # ── 지역 코드 목록 ────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "fetch_area_codes",
            "description": "지원 가능한 지역 코드 목록을 조회합니다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    # ── 접근성 자동 검증 ──────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "validate_accessibility",
            "description": (
                "시설 이름과 주소로 네이버 블로그·지식iN을 자동 크롤링하여 "
                "휠체어 접근성을 검증합니다. "
                "입구 문턱, 좁은 통로, 엘리베이터 고장 등 경고 키워드를 탐지하고, "
                "테이블 높이·통로 폭·엘리베이터 유무 등을 GPT-4o로 추론합니다. "
                "get_detail 호출 직후 자동으로 호출하세요."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "facility_name": {
                        "type": "string",
                        "description": "검증할 시설 이름 (예: '경복궁', '명동 OO식당')",
                    },
                    "address": {
                        "type": "string",
                        "description": "시설 주소 (검색 정확도 향상용, 선택)",
                    },
                    "image_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "시설 대표 이미지 URL 목록 (Vision 분석용, 선택)",
                    },
                },
                "required": ["facility_name"],
            },
        },
    },
]


# ── 함수 실행 라우터 ─────────────────────────────────────────────────────────
def execute_tool(name: str, args: dict) -> str:
    """OpenAI가 요청한 함수를 실행하고 JSON 문자열로 반환한다."""
    if name == "search_places":
        result = tour_api.search_places(**args)
    elif name == "get_detail":
        result = tour_api.get_detail(**args)
    elif name == "fetch_area_codes":
        result = tour_api.fetch_area_codes()
    elif name == "plan_accessible_route":
        result = transport_api.plan_accessible_route(**args)
    elif name == "get_subway_elevator_info":
        result = transport_api.get_subway_elevator_info(**args)
    elif name == "get_disability_taxi_info":
        result = transport_api.get_disability_taxi_info(**args)
    elif name == "validate_accessibility":
        result = naver_validator.validate_accessibility(**args)
    else:
        result = {"error": f"알 수 없는 함수: {name}"}

    return json.dumps(result, ensure_ascii=False, indent=2)


# ── 진행 상태 메시지 ─────────────────────────────────────────────────────────
PROGRESS_MSG = {
    "search_places":            lambda a: f"  [검색] {a.get('area_name')} {a.get('category')} 조회 중...",
    "get_detail":               lambda a: "  [상세] 장소 상세 정보 조회 중...",
    "plan_accessible_route":    lambda a: f"  [경로] {a.get('origin_address')} → {a.get('destination_address')} 무장애 경로 분석 중...",
    "get_subway_elevator_info": lambda a: f"  [엘리베이터] {a.get('station_name')} 엘리베이터 상태 조회 중...",
    "get_disability_taxi_info": lambda a: f"  [콜택시] {a.get('region')} 장애인 콜택시 정보 조회 중...",
    "fetch_area_codes":         lambda a: "  [지역코드] 지역 목록 조회 중...",
    "validate_accessibility":   lambda a: f"  [접근성 검증] '{a.get('facility_name')}' 네이버 리뷰 분석 중...",
}


# ── 환경 변수 검사 ────────────────────────────────────────────────────────────
def check_env() -> bool:
    required = {
        "OPENAI_API_KEY":    "OpenAI API",
        "TOUR_API_KEY":      "한국관광공사 API (data.go.kr)",
    }
    optional = {
        "KAKAO_REST_API_KEY":   "Kakao REST API (경로 안내)",
        "SEOUL_OPEN_API_KEY":   "서울 열린데이터광장 (엘리베이터 상태)",
        "BUS_SERVICE_KEY":      "서울시 버스 API (저상버스 도착)",
        "NAVER_CLIENT_ID":      "네이버 검색 API (접근성 검증)",
        "NAVER_CLIENT_SECRET":  "네이버 검색 API (접근성 검증)",
    }
    placeholders = {"your_openai_api_key_here", "your_tour_api_key_here",
                    "your_kakao_rest_api_key_here", "your_seoul_open_api_key_here",
                    "your_bus_service_key_here",
                    "your_naver_client_id_here", "your_naver_client_secret_here"}

    missing_req = [
        f"  ✗ {k} ({desc})"
        for k, desc in required.items()
        if not os.getenv(k) or os.getenv(k) in placeholders
    ]
    missing_opt = [
        f"  △ {k} ({desc}) — 미설정 시 해당 기능 비활성"
        for k, desc in optional.items()
        if not os.getenv(k) or os.getenv(k) in placeholders
    ]

    if missing_req:
        print("\n[오류] 필수 API 키가 없습니다. .env 파일을 확인하세요:")
        print("\n".join(missing_req))
        return False

    if missing_opt:
        print("\n[경고] 일부 선택 API 키가 설정되지 않았습니다:")
        print("\n".join(missing_opt))
        print()

    return True


# ── 메인 챗봇 루프 ────────────────────────────────────────────────────────────
def run():
    if not check_env():
        return

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("\n" + "=" * 60)
    print("  ♿  무장애 여행 추천 챗봇 '트래블리(Travelly)'")
    print("=" * 60)
    print("장소 추천 + 장애인 맞춤 경로 안내 서비스")
    print("종료: 'q' 또는 '종료'\n")

    greeting = (
        "안녕하세요! 무장애 여행 전문 챗봇 트래블리입니다 ♿\n\n"
        "다음 두 가지 서비스를 제공합니다.\n"
        "  1️⃣  지역별 무장애 관광지·숙박·음식점·문화시설 추천\n"
        "  2️⃣  목적지까지 장애인 맞춤 경로 안내\n"
        "      (저상버스 · 엘리베이터 · 리프트 · 장애인 콜택시)\n\n"
        f"지원 지역: {', '.join(tour_api.AREA_MAP.keys())}\n"
        "어떤 도움이 필요하신가요?"
    )
    print(f"[트래블리] {greeting}\n")

    while True:
        try:
            user_input = input("[나] ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[트래블리] 즐거운 여행 되세요! ♿🌟\n")
            break

        if not user_input:
            continue
        if user_input.lower() in ("q", "quit", "exit", "종료"):
            print("\n[트래블리] 안전하고 편안한 여행 되세요! ♿🌟\n")
            break

        messages.append({"role": "user", "content": user_input})

        # ── OpenAI 응답 루프 (함수 호출 연쇄 처리) ─────────────────────────
        while True:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=2500,
            )

            msg = response.choices[0].message
            messages.append(msg)

            if not msg.tool_calls:
                print(f"\n[트래블리]\n{msg.content}\n")
                break

            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                progress = PROGRESS_MSG.get(fn_name, lambda a: f"  [{fn_name}] 처리 중...")
                print(progress(fn_args))

                result = execute_tool(fn_name, fn_args)
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tool_call.id,
                    "content":      result,
                })


if __name__ == "__main__":
    run()
