"""
Vector DB 데이터 적재 스크립트
- 한국관광공사 API: 전 지역 × 전 카테고리 장소 정보
- 네이버 블로그/뉴스: 최신 무장애 축제 정보
- 장애인 콜택시: 정적 DB 전체

실행: python ingest.py
"""

import time
import vector_store
import tour_api
import transport_api
import naver_validator


def ingest_tour_places() -> int:
    """모든 지역 × 카테고리 조합으로 관광지 수집 후 저장"""
    doc_id = 0
    total = 0

    for area_name in tour_api.AREA_MAP:
        for category in tour_api.CONTENT_TYPE_MAP:
            print(f"  수집 중: {area_name} / {category}", end=" ", flush=True)
            places = tour_api.search_places(area_name, category, num_of_rows=20)

            if places and "error" not in places[0] and "message" not in places[0]:
                for place in places:
                    vector_store.store_tour_place(doc_id, place, area_name)
                    doc_id += 1
                    total += 1
                print(f"→ {len(places)}건 저장")
            else:
                print("→ 결과 없음")

            time.sleep(0.3)  # API rate limit 대응

    return total


def ingest_festivals_from_naver(doc_id_start: int = 20000) -> int:
    """네이버 블로그·뉴스에서 최신 무장애 축제 정보 수집 후 festival_news 컬렉션에 저장"""
    print("  수집 중: 네이버 무장애 축제 블로그/뉴스", end=" ", flush=True)
    items = naver_validator.search_barrier_free_festivals(display=20)

    if not items:
        print("→ 결과 없음 (네이버 API 키 확인 필요)")
        return 0

    for i, item in enumerate(items):
        vector_store.store_festival_news(doc_id_start + i, item)
    print(f"→ {len(items)}건 저장")
    return len(items)


def ingest_transport_info() -> int:
    """장애인 콜택시 정적 DB 저장"""
    total = 0
    for doc_id, (region, info) in enumerate(transport_api.DISABILITY_TAXI_DB.items()):
        print(f"  저장 중: {region} 콜택시 정보")
        vector_store.store_transport_info(doc_id, region, info)
        total += 1
    return total


def main():
    print("=" * 50)
    print("  Vector DB 데이터 적재 시작")
    print("=" * 50)

    print("\n[1/3] 관광지 데이터 수집 중...")
    try:
        tour_count = ingest_tour_places()
        print(f"  완료: 총 {tour_count}건 저장\n")
    except Exception as e:
        print(f"  오류: {e}\n")
        tour_count = 0

    print("[2/3] 최신 무장애 축제 데이터 수집 중 (네이버)...")
    try:
        festival_count = ingest_festivals_from_naver()
        print(f"  완료: 총 {festival_count}건 저장\n")
    except Exception as e:
        print(f"  오류: {e}\n")

    print("[3/3] 교통 지원 정보 저장 중...")
    try:
        transport_count = ingest_transport_info()
        print(f"  완료: 총 {transport_count}건 저장\n")
    except Exception as e:
        print(f"  오류: {e}\n")
        transport_count = 0

    print("=" * 50)
    counts = vector_store.collection_counts()
    print(f"  tour_places     : {counts.get('tour_places', 0)}건")
    print(f"  festival_news   : {counts.get('festival_news', 0)}건")
    print(f"  transport_info  : {counts.get('transport_info', 0)}건")
    print("  Vector DB 적재 완료!")
    print("=" * 50)


if __name__ == "__main__":
    main()
