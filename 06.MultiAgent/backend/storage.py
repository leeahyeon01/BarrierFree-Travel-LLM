"""
JSON 파일 기반 일정 CRUD.
저장 경로: 06.MultiAgent/data/itineraries/
"""
from __future__ import annotations
import os
import json
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "itineraries")
os.makedirs(_STORAGE_DIR, exist_ok=True)


def save_itinerary(itinerary_data: Dict[str, Any]) -> str:
    itinerary_id = itinerary_data.get("id") or str(uuid.uuid4())
    itinerary_data["id"] = itinerary_id
    if "created_at" not in itinerary_data:
        itinerary_data["created_at"] = datetime.now().isoformat()

    with open(_path(itinerary_id), "w", encoding="utf-8") as f:
        json.dump(itinerary_data, f, ensure_ascii=False, indent=2)
    return itinerary_id


def list_itineraries() -> List[Dict[str, Any]]:
    summaries = []
    for fname in os.listdir(_STORAGE_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(_STORAGE_DIR, fname), "r", encoding="utf-8") as f:
            data = json.load(f)
        summaries.append({
            "id": data.get("id"),
            "destination": data.get("destination"),
            "duration_days": data.get("duration_days"),
            "created_at": data.get("created_at"),
            "accessibility_needs": data.get("accessibility_needs", []),
        })
    return sorted(summaries, key=lambda x: x.get("created_at") or "", reverse=True)


def get_itinerary(itinerary_id: str) -> Optional[Dict[str, Any]]:
    p = _path(itinerary_id)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_itinerary(itinerary_id: str) -> bool:
    p = _path(itinerary_id)
    if not os.path.exists(p):
        return False
    os.remove(p)
    return True


def _path(itinerary_id: str) -> str:
    return os.path.join(_STORAGE_DIR, f"{itinerary_id}.json")
