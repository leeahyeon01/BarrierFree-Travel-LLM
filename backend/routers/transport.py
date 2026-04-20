from fastapi import APIRouter
import transport_api

router = APIRouter()


@router.post("/route")
def plan_route(origin_address: str, destination_address: str):
    return transport_api.plan_accessible_route(origin_address, destination_address)


@router.get("/elevator/{station_name}")
def get_elevator(station_name: str):
    return transport_api.get_subway_elevator_info(station_name)


@router.get("/taxi/{region}")
def get_taxi(region: str):
    return transport_api.get_disability_taxi_info(region)
