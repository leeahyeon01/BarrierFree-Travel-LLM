from fastapi import APIRouter
import tour_api

router = APIRouter()


@router.get("/areas")
def get_areas():
    return tour_api.fetch_area_codes()


@router.post("/search")
def search_places(area_name: str, category: str, num_of_rows: int = 10):
    return tour_api.search_places(area_name, category, num_of_rows)


@router.get("/detail/{content_id}")
def get_detail(content_id: str):
    return tour_api.get_detail(content_id)
