"""
한국관광공사 무장애여행 API 클라이언트 (KorWithService2)
"""

import os
from datetime import date
import requests
from dotenv import load_dotenv

load_dotenv()

TOUR_API_KEY = os.getenv("TOUR_API_KEY")
BASE_URL = "https://apis.data.go.kr/B551011/KorWithService2"

# 지역 코드 매핑
AREA_MAP = {
    "서울": "1",
    "인천": "2",
    "대전": "3",
    "대구": "4",
    "광주": "5",
    "부산": "6",
    "울산": "7",
    "세종": "8",
    "경기": "31",
    "강원": "32",
    "충북": "33",
    "충남": "34",
    "전북": "35",
    "전남": "36",
    "경북": "37",
    "경남": "38",
    "제주": "39",
}

# 콘텐츠 타입 매핑
CONTENT_TYPE_MAP = {
    "관광지": "12",
    "문화시설": "14",
    "축제": "15",
    "숙박": "32",
    "음식점": "39",
}

COMMON_PARAMS = {
    "MobileOS": "ETC",
    "MobileApp": "BarrierFreeTravel",
    "_type": "json",
}


def _get(endpoint: str, extra_params: dict) -> dict:
    """공통 GET 요청 처리"""
    params = {
        "ServiceKey": TOUR_API_KEY,
        **COMMON_PARAMS,
        **extra_params,
    }
    try:
        resp = requests.get(
            f"{BASE_URL}/{endpoint}",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.Timeout:
        return {"error": "API 응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."}
    except requests.RequestException as e:
        return {"error": f"API 호출 실패: {str(e)}"}
    except ValueError:
        return {"error": "API 응답을 파싱할 수 없습니다."}


def fetch_area_codes() -> list[dict]:
    """지역 코드 목록 조회 (areaCode2)"""
    data = _get("areaCode2", {"numOfRows": 20, "pageNo": 1})
    if "error" in data:
        return [data]

    items = data.get("response", {}).get("body", {}).get("items", {})
    if not items:
        return [{"message": "지역 코드 데이터가 없습니다."}]

    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]

    return [{"지역명": i.get("name", ""), "코드": i.get("code", "")} for i in item_list]


def search_festivals(area_name: str | None = None, num_of_rows: int = 20) -> list[dict]:
    """
    현재 날짜 기준 진행 중 또는 예정된 무장애 축제 검색 (searchFestival2)

    Args:
        area_name: 지역명 (None이면 전국)
        months_ahead: 오늘부터 몇 개월 앞까지 조회 (기본 3개월)
        num_of_rows: 조회 건수 (최대 20)
    """
    today = date.today().strftime("%Y%m%d")
    extra: dict = {
        "numOfRows": min(num_of_rows, 20),
        "pageNo": 1,
        "eventStartDate": today,
    }
    if area_name:
        area_code = AREA_MAP.get(area_name)
        if not area_code:
            available = ", ".join(AREA_MAP.keys())
            return [{"error": f"'{area_name}' 지역을 찾을 수 없습니다. 사용 가능한 지역: {available}"}]
        extra["areaCode"] = area_code

    data = _get("searchFestival2", extra)
    if "error" in data:
        return [data]

    items = data.get("response", {}).get("body", {}).get("items", {})
    if not items:
        region_label = area_name or "전국"
        return [{"message": f"{region_label}에서 현재 진행/예정된 무장애 축제 정보가 없습니다."}]

    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]

    results = []
    for item in item_list:
        addr = (item.get("addr1", "") + " " + item.get("addr2", "")).strip()
        results.append({
            "이름": item.get("title", ""),
            "주소": addr if addr else "주소 정보 없음",
            "전화번호": item.get("tel", "정보 없음"),
            "시작일": item.get("eventstartdate", ""),
            "종료일": item.get("eventenddate", ""),
            "content_id": item.get("contentid", ""),
            "카테고리": "축제",
            "image": item.get("firstimage", ""),
        })
    return results


def search_places(area_name: str, category: str, num_of_rows: int = 10) -> list[dict]:
    """
    지역·카테고리별 무장애 여행 장소 검색 (areaBasedList2)

    Args:
        area_name: 지역명 (예: 서울, 부산, 제주)
        category: 카테고리 (관광지 / 문화시설 / 숙박 / 음식점)
        num_of_rows: 조회 건수 (최대 20)
    """
    area_code = AREA_MAP.get(area_name)
    content_type_id = CONTENT_TYPE_MAP.get(category)

    if not area_code:
        available = ", ".join(AREA_MAP.keys())
        return [{"error": f"'{area_name}' 지역을 찾을 수 없습니다. 사용 가능한 지역: {available}"}]

    if not content_type_id:
        available = ", ".join(CONTENT_TYPE_MAP.keys())
        return [{"error": f"'{category}' 카테고리를 찾을 수 없습니다. 사용 가능: {available}"}]

    data = _get(
        "areaBasedList2",
        {
            "numOfRows": min(num_of_rows, 20),
            "pageNo": 1,
            "areaCode": area_code,
            "contentTypeId": content_type_id,
        },
    )

    if "error" in data:
        return [data]

    items = data.get("response", {}).get("body", {}).get("items", {})
    if not items:
        return [{"message": f"{area_name}에서 무장애 {category} 정보를 찾지 못했습니다."}]

    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]

    results = []
    for item in item_list:
        addr = (item.get("addr1", "") + " " + item.get("addr2", "")).strip()
        results.append(
            {
                "이름": item.get("title", ""),
                "주소": addr if addr else "주소 정보 없음",
                "전화번호": item.get("tel", "정보 없음"),
                "content_id": item.get("contentid", ""),
                "카테고리": category,
                "image": item.get("firstimage", ""),
            }
        )

    return results


def search_random_places(category: str, count: int = 6) -> list[dict]:
    """
    전국 랜덤 지역에서 카테고리별 무장애 장소를 가져온다.
    이미지가 있는 결과만 필터링하여 count개 반환.
    """
    import random
    areas = list(AREA_MAP.keys())
    random.shuffle(areas)

    results = []
    for area in areas:
        if len(results) >= count:
            break
        places = search_places(area, category, num_of_rows=20)
        with_img = [p for p in places if p.get("image")]
        results.extend(with_img)

    random.shuffle(results)
    return results[:count]


def get_detail(content_id: str) -> dict:
    """
    장소 상세 정보 조회 (detailCommon2)

    Args:
        content_id: 조회할 장소의 contentId
    """
    data = _get(
        "detailCommon2",
        {
            "contentId": content_id,
        },
    )

    if "error" in data:
        return data

    items = data.get("response", {}).get("body", {}).get("items", {})
    if not items:
        return {"error": "상세 정보를 찾을 수 없습니다."}

    item = items.get("item", [])
    if isinstance(item, list) and item:
        item = item[0]
    elif isinstance(item, list):
        return {"error": "상세 정보가 비어 있습니다."}

    overview = item.get("overview", "")
    if overview and len(overview) > 600:
        overview = overview[:600] + "..."

    images = []
    if item.get("firstimage"):
        images.append(item["firstimage"])
    if item.get("firstimage2") and item.get("firstimage2") != item.get("firstimage"):
        images.append(item["firstimage2"])

    return {
        "이름": item.get("title", ""),
        "주소": item.get("addr1", ""),
        "전화번호": item.get("tel", "정보 없음"),
        "홈페이지": item.get("homepage", "정보 없음"),
        "개요": overview if overview else "정보 없음",
        "images": images,
    }
