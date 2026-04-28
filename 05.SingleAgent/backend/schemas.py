from pydantic import BaseModel, Field
from typing import List, Optional

class TravelRequest(BaseModel):
    destination: str = Field(description="여행 목적지 (예: 제주도, 서울)")
    duration: str = Field(description="여행 기간 (예: 1박 2일)")
    accessibility_needs: List[str] = Field(description="필요한 접근성 조건 (예: 휠체어, 엘리베이터, 단차 없음)")

class ValidationResult(BaseModel):
    is_valid: bool = Field(description="검증 통과 여부")
    feedback: str = Field(description="실패 사유 또는 개선 권고사항")
