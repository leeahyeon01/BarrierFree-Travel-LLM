"""
장애인 무장애 이동 지원 통합 API 모듈
- Kakao Local API     : 주소→좌표, 주변 장소 검색
- Kakao Mobility API  : 자동차 경로(거리·시간·요금)
- 서울시 버스 API      : 저상버스 도착 정보 (busType 필터링)
- 서울 열린데이터광장  : 지하철 엘리베이터 위치·고장 상태
- 장애인 콜택시        : 지역별 정적 데이터
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

KAKAO_KEY    = os.getenv("KAKAO_REST_API_KEY", "")
SEOUL_KEY    = os.getenv("SEOUL_OPEN_API_KEY", "")
BUS_SVC_KEY  = os.getenv("BUS_SERVICE_KEY", "")
ODSAY_KEY    = os.getenv("ODSAY_API_KEY", "")

KAKAO_HDR = {"Authorization": f"KakaoAK {KAKAO_KEY}"}

# 저상버스 busType 코드 (서울시 버스 API 기준)
LOW_FLOOR_BUS_TYPES = {"1", "2"}   # 1=일반저상, 2=굴절(대형저상)

# ── 지역별 장애인 콜택시 (정적 데이터) ─────────────────────────────────────
DISABILITY_TAXI_DB = {
    "서울":  {"이름": "서울시 장애인 콜택시",      "전화": "1588-4388", "앱": "서울동행앱"},
    "부산":  {"이름": "부산 교통약자이동지원센터", "전화": "051-580-5656", "앱": "없음"},
    "대구":  {"이름": "대구시 장애인 콜택시",      "전화": "053-350-5870", "앱": "없음"},
    "인천":  {"이름": "인천 교통약자이동지원",     "전화": "032-424-2022", "앱": "없음"},
    "광주":  {"이름": "광주 교통약자이동지원",     "전화": "062-600-9000", "앱": "없음"},
    "대전":  {"이름": "대전 교통약자이동지원",     "전화": "042-270-6363", "앱": "없음"},
    "울산":  {"이름": "울산 교통약자이동지원",     "전화": "052-710-6010", "앱": "없음"},
    "경기":  {"이름": "경기도 장애인 콜택시",      "전화": "031-8015-0700", "앱": "경기도 콜택시 앱"},
    "제주":  {"이름": "제주 교통약자이동지원",     "전화": "064-728-7979", "앱": "없음"},
    "강원":  {"이름": "강원도 교통약자이동지원",   "전화": "033-749-3100", "앱": "없음"},
    "충북":  {"이름": "충북 교통약자이동지원",     "전화": "043-220-4000", "앱": "없음"},
    "충남":  {"이름": "충남 교통약자이동지원",     "전화": "041-635-6000", "앱": "없음"},
    "전북":  {"이름": "전북 교통약자이동지원",     "전화": "063-280-3000", "앱": "없음"},
    "전남":  {"이름": "전남 교통약자이동지원",     "전화": "061-286-0800", "앱": "없음"},
    "경북":  {"이름": "경북 교통약자이동지원",     "전화": "054-840-8000", "앱": "없음"},
    "경남":  {"이름": "경남 교통약자이동지원",     "전화": "055-279-2900", "앱": "없음"},
    "세종":  {"이름": "세종 교통약자이동지원",     "전화": "044-300-5000", "앱": "없음"},
}
DEFAULT_TAXI = {
    "이름": "지역 교통약자이동지원센터",
    "전화": "지자체 복지과 문의",
    "앱": "각 지자체 확인",
}


# ── 공통 HTTP 요청 ──────────────────────────────────────────────────────────
def _get(url: str, params: dict = None, headers: dict = None, timeout: int = 10) -> dict:
    try:
        r = requests.get(url, params=params or {}, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.Timeout:
        return {"error": "API 응답 시간 초과. 잠시 후 다시 시도해 주세요."}
    except requests.RequestException as e:
        return {"error": f"API 호출 실패: {str(e)}"}
    except ValueError:
        return {"error": "API 응답 파싱 실패 (JSON 아님)"}


# ════════════════════════════════════════════════════════════════════════════
# 1. Kakao API
# ════════════════════════════════════════════════════════════════════════════

def geocode(address: str) -> dict:
    """
    주소 → 위경도 변환 (Kakao Local 주소 검색 API)
    주소 검색 실패 시 키워드 검색으로 자동 폴백.
    Returns: {name, address, lat, lng, region_1depth}
    """
    # 1차: 주소 검색
    data = _get(
        "https://dapi.kakao.com/v2/local/search/address.json",
        params={"query": address, "size": 1},
        headers=KAKAO_HDR,
    )
    docs = data.get("documents", []) if "error" not in data else []

    # 2차: 키워드 검색 폴백
    if not docs:
        data = _get(
            "https://dapi.kakao.com/v2/local/search/keyword.json",
            params={"query": address, "size": 1},
            headers=KAKAO_HDR,
        )
        docs = data.get("documents", []) if "error" not in data else []
        if not docs:
            return {"error": f"'{address}' 위치를 찾을 수 없습니다."}
        doc = docs[0]
        return {
            "name":            doc.get("place_name", address),
            "address":         doc.get("address_name", ""),
            "lat":             float(doc.get("y", 0)),
            "lng":             float(doc.get("x", 0)),
            "region_1depth":   doc.get("address_name", "서울").split()[0],
        }

    doc = docs[0]
    road = doc.get("road_address") or doc.get("address") or {}
    return {
        "name":          address,
        "address":       doc.get("address_name", ""),
        "lat":           float(doc.get("y", 0)),
        "lng":           float(doc.get("x", 0)),
        "region_1depth": road.get("region_1depth_name", "서울"),
    }


def get_car_route(origin_lng: float, origin_lat: float,
                  dest_lng: float, dest_lat: float) -> dict:
    """
    자동차 경로 탐색 (Kakao Mobility Directions API)
    Returns: {distance_km, duration_min, taxi_fare}
    """
    data = _get(
        "https://apis-navi.kakaomobility.com/v1/directions",
        params={
            "origin":      f"{origin_lng},{origin_lat}",
            "destination": f"{dest_lng},{dest_lat}",
            "priority":    "RECOMMEND",
        },
        headers=KAKAO_HDR,
    )
    if "error" in data:
        return data

    routes = data.get("routes", [])
    if not routes:
        return {"error": "경로를 찾을 수 없습니다."}

    summary = routes[0].get("summary", {})
    return {
        "distance_km":  round(summary.get("distance", 0) / 1000, 1),
        "duration_min": round(summary.get("duration", 0) / 60),
        "taxi_fare":    summary.get("fare", {}).get("taxi", 0),
    }

# ════════════════════════════════════════════════════════════════════════════
# 1.5 ODsay 대중교통 길찾기 API
# ════════════════════════════════════════════════════════════════════════════
def get_odsay_transit_route(sx: float, sy: float, ex: float, ey: float) -> dict:
    """ODsay API를 사용한 대중교통 리스트 반환 (기차, 고속버스, 지하철 환승 포함)"""
    if not ODSAY_KEY or ODSAY_KEY == "your_odsay_api_key_here":
        return {"error": "ODsay API 키가 설정되지 않음"}

    url = "https://api.odsay.com/v1/api/searchPubTransPathT"
    data = _get(url, params={"apiKey": ODSAY_KEY, "SX": sx, "SY": sy, "EX": ex, "EY": ey})
    
    if "error" in data or "result" not in data:
        return {"error": "대중교통 경로를 찾을 수 없거나 제공되지 않는 구간입니다."}
        
    path_list = data["result"].get("path", [])
    if not path_list:
        return {"error": "이용 가능한 대중교통 경로가 없습니다."}
        
    # 최적 경로(첫 번째 경로) 가져오기
    best_path = path_list[0]
    info = best_path.get("info", {})
    
    steps = []
    for sub in best_path.get("subPath", []):
        traffic_type = sub.get("trafficType")
        if traffic_type == 3: # 도보
            steps.append(f"도보 {sub.get('sectionTime', 0)}분")
        elif traffic_type in (1, 2): # 1:지하철, 2:버스
            steps.append(f"[{sub.get('lane', [{}])[0].get('name', '대중교통')}] {sub.get('startName')} 탑승 → {sub.get('endName')} 하차")
        elif traffic_type in (4, 5, 6, 7): # 4:기차, 5:KTX, 6:고속버스, 7:시외/항공/해운
            lane_name = ""
            if traffic_type == 4 or traffic_type == 5: lane_name = "🚂 기차/KTX"
            elif traffic_type == 6 or traffic_type == 7: lane_name = "🚍 고속/시외버스"
            steps.append(f"{lane_name} ({sub.get('startName')} → {sub.get('endName')})")

    return {
        "총_소요시간": f"{info.get('totalTime', 0)}분",
        "총_요금": f"{info.get('payment', 0)}원",
        "경로_요약": f"{info.get('firstStartStation')} 탑승 → {info.get('lastEndStation')} 하차",
        "상세_환승_단계": " / ".join(steps)
    }

# ════════════════════════════════════════════════════════════════════════════
# 2. 서울시 버스 API (data.go.kr - ws.bus.go.kr)
# ════════════════════════════════════════════════════════════════════════════

def find_nearby_bus_stops(lat: float, lng: float, radius: int = 500) -> list:
    """
    좌표 기반 근처 버스 정류장 조회 (서울시 버스 정보 시스템)
    Returns: [{정류장명, arsId, stId}, ...]
    """
    data = _get(
        "http://ws.bus.go.kr/api/rest/stationinfo/getStationByPos",
        params={
            "ServiceKey": BUS_SVC_KEY,
            "tmX":        lng,
            "tmY":        lat,
            "radius":     radius,
            "resultType": "json",
        },
    )
    if "error" in data:
        return []

    items = data.get("msgBody", {}).get("itemList", [])
    if isinstance(items, dict):
        items = [items]
    if not items:
        # items가 None이거나 빈 리스트일 때 안전하게 빈 리스트 반환
        return []

    return [
        {
            "정류장명": i.get("stNm", ""),
            "arsId":    i.get("arsId", ""),
            "stId":     i.get("stId", ""),
        }
        for i in items[:5]
    ]


def get_low_floor_bus_arrivals(st_id: str) -> list:
    """
    저상버스 도착 정보 조회 (서울시 버스 getLowArrInfoByStId)
    busType 1=일반저상, 2=굴절버스(대형저상) 만 필터링
    Returns: [{버스번호, 저상버스여부, 첫번째도착, 두번째도착}, ...]
    """
    data = _get(
        "http://ws.bus.go.kr/api/rest/arrive/getLowArrInfoByStId",
        params={
            "ServiceKey": BUS_SVC_KEY,
            "stId":       st_id,
            "resultType": "json",
        },
    )
    if "error" in data:
        return [{"error": data["error"]}]

    items = data.get("msgBody", {}).get("itemList", [])
    if not items:
        return [{"message": "현재 이 정류장에 저상버스 도착 정보가 없습니다."}]
    if isinstance(items, dict):
        items = [items]

    results = []
    for item in items:
        bus_type = str(item.get("busType", ""))
        is_low   = bus_type in LOW_FLOOR_BUS_TYPES
        results.append({
            "버스번호":    item.get("rtNm", ""),
            "busType":    bus_type,
            "저상버스":   "✅ 저상버스" if is_low else "일반버스",
            "첫번째도착": item.get("arrmsg1", ""),
            "두번째도착": item.get("arrmsg2", ""),
        })

    # 저상버스 우선 정렬
    results.sort(key=lambda x: 0 if "저상버스" in x["저상버스"] else 1)
    return results


# ════════════════════════════════════════════════════════════════════════════
# 3. 서울 열린데이터광장 - 지하철 엘리베이터 / 리프트
# ════════════════════════════════════════════════════════════════════════════

def get_subway_elevator_info(station_name: str) -> list:
    """
    지하철역 엘리베이터 위치 정보 (서울 열린데이터광장 tbTraficElevator)
    계단 없는 경로(엘리베이터 우선) 안내에 사용.
    """
    clean = station_name.replace("역", "").replace("(", "").split(")")[0].strip()
    data = _get(
        f"http://openapi.seoul.go.kr:8088/{SEOUL_KEY}/json/tbTraficElevator/1/20/{clean}/",
    )
    if "error" in data:
        return [{"error": data["error"]}]

    result = data.get("tbTraficElevator", {})
    code   = result.get("RESULT", {}).get("CODE", "")
    if code != "INFO-000":
        return [{"message": f"'{station_name}' 엘리베이터 정보 없음 (서울 외 지역이거나 역명 확인 필요)"}]

    rows = result.get("row", [])
    if not rows:
        return [{"message": f"'{station_name}' 엘리베이터 데이터 없음"}]

    return [
        {
            "역명":       row.get("STATN_NM", ""),
            "호선":       row.get("LINE_NUM", ""),
            "위치":       row.get("ELEV_LOCATION", ""),
            "엘리베이터번호": row.get("ELEV_NO", ""),
        }
        for row in rows
    ]


def get_lift_fault_status(station_name: str) -> list:
    """
    지하철역 엘리베이터·리프트 고장/점검 정보 (서울 열린데이터광장)
    ListElevatorFaultInfo 서비스 사용.
    """
    clean = station_name.replace("역", "").strip()
    data = _get(
        f"http://openapi.seoul.go.kr:8088/{SEOUL_KEY}/json/ListElevatorFaultInfo/1/10/{clean}/",
    )
    if "error" in data:
        return [{"error": data["error"]}]

    result = data.get("ListElevatorFaultInfo", {})
    code   = result.get("RESULT", {}).get("CODE", "")
    if code != "INFO-000":
        return [{"message": f"'{station_name}' 고장·점검 정보 없음 (정상 운행 중일 수 있습니다)"}]

    rows = result.get("row", [])
    if not rows:
        return [{"status": "정상", "message": f"'{station_name}' 현재 고장·점검 중인 설비 없음"}]

    return [
        {
            "역명":     row.get("STATN_NM", ""),
            "위치":     row.get("LOCATION", ""),
            "상태":     row.get("STATUS_NM", ""),
            "고장시작": row.get("FAULT_BEGIN_DT", ""),
            "복구예정": row.get("RECOVERY_SHEDULE_DT", "미정"),
        }
        for row in rows
    ]


# ════════════════════════════════════════════════════════════════════════════
# 4. 장애인 콜택시 (정적 DB)
# ════════════════════════════════════════════════════════════════════════════

def get_disability_taxi_info(region: str) -> dict:
    """지역명으로 장애인 콜택시 정보 반환"""
    for key, val in DISABILITY_TAXI_DB.items():
        if key in region:
            return val
    return DEFAULT_TAXI


# ════════════════════════════════════════════════════════════════════════════
# 5. 통합 무장애 경로 안내 (오케스트레이터)
# ════════════════════════════════════════════════════════════════════════════

def plan_accessible_route(origin_address: str, destination_address: str) -> dict:
    """
    출발지 → 목적지 무장애 경로 통합 안내

    수행 순서:
    1. Kakao 주소→좌표 변환
    2. 자동차 경로(거리·시간·예상요금)
    3. 출발지 근처 저상버스 정류장 + 도착 정보
    4. 목적지 역 엘리베이터 위치
    5. 해당 역 리프트/엘리베이터 고장 현황
    6. 장애인 콜택시 정보
    7. 요약 참고사항

    Returns: 최종 결과 딕셔너리
    """
    result = {
        "출발지":       origin_address,
        "목적지":       destination_address,
        "경로":         {},
        "저상버스":     [],
        "주변정류장":   [],
        "엘리베이터":   [],
        "리프트_고장":  [],
        "장애인콜택시": {},
        "참고사항":     [],
    }

    # ① 좌표 변환
    origin = geocode(origin_address)
    dest   = geocode(destination_address)

    if "error" in origin:
        result["참고사항"].append(f"⚠ 출발지 오류: {origin['error']}")
        return result
    if "error" in dest:
        result["참고사항"].append(f"⚠ 목적지 오류: {dest['error']}")
        return result

    result["출발지_좌표"] = {"lat": origin["lat"], "lng": origin["lng"]}
    result["목적지_좌표"] = {"lat": dest["lat"],   "lng": dest["lng"]}

    # ② 자동차 경로 및 대중교통 경로 (ODsay)
    route = get_car_route(origin["lng"], origin["lat"], dest["lng"], dest["lat"])
    result["자동차_경로"] = route
    
    transit_route = get_odsay_transit_route(origin["lng"], origin["lat"], dest["lng"], dest["lat"])
    result["대중교통_경로"] = transit_route

    # ③ 출발지 근처 저상버스
    stops = find_nearby_bus_stops(origin["lat"], origin["lng"])
    result["주변정류장"] = stops

    if stops:
        first_stop = stops[0]
        if first_stop.get("stId"):
            arrivals = get_low_floor_bus_arrivals(first_stop["stId"])
            result["저상버스"] = {
                "정류장명": first_stop["정류장명"],
                "도착정보": arrivals,
            }

    # ④⑤ 출발지와 목적지 모두가 지하철역인지 확인하여 엘리베이터 정보 조회
    elev_results = []
    fault_results = []
    
    for loc_hint in (origin_address, destination_address):
        if any(kw in loc_hint for kw in ("역", "지하철", "metro", "Metro")):
            elev_results.extend(get_subway_elevator_info(loc_hint))
            fault_results.extend(get_lift_fault_status(loc_hint))
            
    if elev_results:
        result["엘리베이터"] = elev_results
        result["리프트_고장"] = fault_results
    else:
        result["참고사항"].append(
            "출발지 또는 목적지가 관할 지하철 API 적용 대상이 아니거나, 현재 서울시 API 서버 점검/오류로 엘리베이터 정보를 조회하지 못했습니다."
        )

    # ⑥ 장애인 콜택시
    region = dest.get("region_1depth", origin.get("region_1depth", "서울"))
    result["장애인콜택시"] = get_disability_taxi_info(region)

    # ⑦ 참고사항 자동 생성
    if "distance_km" in route:
        dist, dur = route["distance_km"], route["duration_min"]
        if dist <= 1.5:
            result["참고사항"].append("가까운 거리 (1.5km 이하) — 전동휠체어 직접 이동 가능합니다.")
        elif dist <= 5:
            result["참고사항"].append("단거리 이동 — 장애인 콜택시 이용이 가장 편리합니다.")
        if dur <= 10:
            result["참고사항"].append("이동 시간이 짧습니다. 콜택시 예약 시 여유를 두고 신청하세요.")

    return result
