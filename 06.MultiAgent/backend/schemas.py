from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


class TravelIntent(BaseModel):
    destination: str
    duration_days: int
    accessibility_needs: List[str]
    group_types: List[str]          # wheelchair / elderly / infant
    special_requests: Optional[str] = None


class PlaceInfo(BaseModel):
    name: str
    category: str                   # tourist / restaurant / transport
    accessibility_summary: str
    source: Optional[str] = None


class ValidationResult(BaseModel):
    place_name: str
    is_safe: bool
    accessibility_score: Optional[float] = None
    issues: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    inference_note: Optional[str] = None


class DaySession(BaseModel):
    session: str                    # 오전 / 오후 / 저녁
    place: str
    duration_hours: float
    accessibility_notes: str
    validation_status: str          # ✅ or 🔴


class ItineraryDay(BaseModel):
    day: int
    sessions: List[DaySession]
    total_hours: float


class Itinerary(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    destination: str
    duration_days: int
    accessibility_needs: List[str]
    group_types: List[str]
    days: List[ItineraryDay]
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    summary_markdown: Optional[str] = None


# ── 평가 스키마: 코드 검증 항목 vs LLM 판단 항목 ──────────────────────────────

class EvalCodeChecks(BaseModel):
    """코드 검증 항목 — 외부 API 없이 규칙으로 판단"""
    precision_at_k: Optional[float] = None
    recall_at_k: Optional[float] = None
    mrr: Optional[float] = None
    session_count_ok: bool
    daily_time_ok: bool
    group_composition_ok: bool


class EvalLLMChecks(BaseModel):
    """LLM 판단 항목 — GPT 호출 필요"""
    faithfulness: Optional[float] = None
    coverage: Optional[float] = None


class EvalReport(BaseModel):
    code_checks: EvalCodeChecks
    llm_checks: EvalLLMChecks
    overall_pass: bool


# ── API 스키마 ─────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    complete: bool
    itinerary: Optional[Dict[str, Any]] = None
    validation_result: Optional[Dict[str, Any]] = None
