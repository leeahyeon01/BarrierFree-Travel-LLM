import json

def search_rag(query: str, accessibility_needs: list) -> str:
    """내부 RAG(Qdrant)를 검색하여 접근성이 확보된 장소를 찾습니다."""
    # TODO: 실제 vector_store.py를 연결하여 Qdrant 검색 로직 연동
    return f"[RAG 검색 결과] '{query}' 주변 정보 - 추천 장소 1: 휠체어 경사로가 있는 A관광지, 추천 장소 2: 엘리베이터가 있는 B식당"

def search_web(query: str) -> str:
    """Tavily 또는 외부 API를 통해 최신 배리어프리 정보를 찾습니다."""
    return f"[웹 검색 결과] '{query}' 관련 최근 배리어프리 행사 정보 및 최신 교통편 업데이트..."

def validate_course(course_text: str) -> str:
    """생성된 여행 코스의 휠체어 이동 가능성, 시간/거리를 검증합니다."""
    # 간단한 시뮬레이션: '계단' 단어가 포함되면 검증 실패
    if "계단" in course_text:
        return json.dumps({
            "is_valid": False, 
            "feedback": "경로에 '계단'이 포함되어 휠체어 이동이 불가능합니다. 단차가 없는 대안 경로를 찾아주세요."
        }, ensure_ascii=False)
    
    return json.dumps({
        "is_valid": True, 
        "feedback": "모든 접근성 조건 만족. 동선 타당함."
    }, ensure_ascii=False)

tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "search_rag",
            "description": "배리어프리 장소(관광지, 음식점) DB를 검색합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색할 지역 또는 장소 키워드"},
                    "accessibility_needs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "필요한 접근성 옵션 (예: 휠체어, 시각장애)"
                    }
                },
                "required": ["query", "accessibility_needs"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "최신 외부 웹 정보를 검색합니다. 실시간 교통이나 최신 행사가 필요할 때 사용합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색어"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_course",
            "description": "생성된 여행 코스가 규칙(접근성, 동선)을 만족하는지 검증합니다. 코스 제안 전 반드시 이 도구를 호출하세요.",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_text": {"type": "string", "description": "검증할 여행 코스 전체 내용"}
                },
                "required": ["course_text"]
            }
        }
    }
]

available_functions = {
    "search_rag": search_rag,
    "search_web": search_web,
    "validate_course": validate_course,
}
