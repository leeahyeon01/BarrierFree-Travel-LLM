from fastapi import APIRouter
from pydantic import BaseModel
import naver_validator

router = APIRouter()


class ValidationRequest(BaseModel):
    facility_name: str
    address: str = ""
    image_urls: list[str] = []


@router.post("")
def validate_accessibility(req: ValidationRequest):
    return naver_validator.validate_accessibility(
        facility_name=req.facility_name,
        address=req.address,
        image_urls=req.image_urls or None,
    )
