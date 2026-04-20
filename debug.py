import os
from dotenv import load_dotenv
import transport_api
import tour_api
import json

load_dotenv()

print("--- Testing Kakao API ---")
kakao_res = transport_api.geocode("강남역")
print("Geocode:", json.dumps(kakao_res, ensure_ascii=False))
if "error" not in kakao_res:
    coord = transport_api.get_car_route(127.0276, 37.4979, 127.059, 37.512)
    print("Driving Route:", json.dumps(coord, ensure_ascii=False))

print("\n--- Testing Tour API ---")
tour_res = tour_api.search_places("서울", "관광지", 2)
print("Tour API:", json.dumps(tour_res, ensure_ascii=False))

print("\n--- Testing Seoul Bus Opendata ---")
bus_res = transport_api.find_nearby_bus_stops(37.4979, 127.0276, 500)
print("Bus:", json.dumps(bus_res, ensure_ascii=False)[:300])

print("\n--- Testing Seoul Subway Elevator ---")
subway_res = transport_api.get_subway_elevator_info("강남역")
print("Subway:", json.dumps(subway_res, ensure_ascii=False)[:300])
